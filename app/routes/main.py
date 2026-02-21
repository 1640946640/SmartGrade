import os
import time
import json
import shutil
import uuid
import threading
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from werkzeug.utils import secure_filename

from app.config import Config
from app.utils.file_utils import allowed_file, allowed_answer_file, merge_images_vertically
from app.services.grading_service import run_grading_task, grading_tasks
from app.services.report_service import ReportGenerator

bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

@bp.route('/favicon.ico')
def favicon():
    """处理favicon.ico请求，防止404"""
    # static folder is at project root
    return send_file(os.path.join(Config.BASE_DIR, 'static', 'favicon.svg'), mimetype='image/svg+xml')

@bp.route('/')
def index():
    """首页：显示上传界面"""
    return render_template('index.html')

@bp.route('/upload', methods=['POST'])
def upload_file():
    """上传试卷并启动后台批改任务（支持多张图片）"""
    try:
        if 'exam_image' not in request.files:
            return jsonify({'success': False, 'error': '未找到文件部分'})
        
        files = request.files.getlist('exam_image')
        
        # 过滤掉空文件
        valid_files = [f for f in files if f.filename != '']
        
        if not valid_files:
            return jsonify({'success': False, 'error': '未选择文件'})
            
        saved_paths = []
        
        # 处理所有上传的文件
        for file in valid_files:
            if file and allowed_file(file.filename):
                ext = os.path.splitext(file.filename)[1].lower()
                if not ext:
                    ext = '.jpg'
                # 临时保存
                temp_filename = f"temp_{uuid.uuid4()}{ext}"
                filepath = os.path.join(Config.UPLOAD_FOLDER, temp_filename)
                file.save(filepath)
                saved_paths.append(filepath)
            else:
                # 如果有任何非法文件，清理已保存的文件并返回错误
                for path in saved_paths:
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except:
                        pass
                return jsonify({'success': False, 'error': '文件类型不支持'})
        
        # 确定最终的文件名和路径
        final_filename = f"{uuid.uuid4()}.jpg"
        final_filepath = os.path.join(Config.UPLOAD_FOLDER, final_filename)
        
        if len(saved_paths) == 1:
            # 只有一个文件，直接重命名
            shutil.move(saved_paths[0], final_filepath)
        else:
            # 多个文件，合并
            success = merge_images_vertically(saved_paths, final_filepath)
            if not success:
                # 清理
                for path in saved_paths:
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except:
                        pass
                return jsonify({'success': False, 'error': '图片合并失败'})
            
            # 删除临时文件
            for path in saved_paths:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except:
                    pass
        
        # 获取参数
        question_count_input = request.form.get('question_count', '').strip()
        max_score_input = request.form.get('max_score', '').strip()
        
        # 处理标准答案文件
        answer_file_path = None
        if 'answer_file' in request.files:
            ans_file = request.files['answer_file']
            if ans_file and ans_file.filename != '' and allowed_answer_file(ans_file.filename):
                ans_filename = secure_filename(ans_file.filename)
                # 使用 UUID 避免冲突
                ans_save_name = f"{uuid.uuid4()}_{ans_filename}"
                answer_file_path = os.path.join(Config.ANSWERS_FOLDER, ans_save_name)
                ans_file.save(answer_file_path)
                logger.info(f"上传了标准答案: {answer_file_path}")
        
        if question_count_input == '':
            question_count = None
        else:
            question_count = int(question_count_input)
            
        if max_score_input == '':
            max_score = None
        else:
            max_score = float(max_score_input)
            
        # 获取选择的模型
        selected_models = request.form.getlist('models')
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        grading_tasks[task_id] = {
            'status': 'processing',
            'progress': 0,
            'message': '正在初始化...',
            'filename': final_filename
        }
        
        # 启动后台线程
        thread = threading.Thread(
            target=run_grading_task,
            args=(task_id, final_filepath, final_filename, question_count, max_score, selected_models, answer_file_path)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id
        })
                
    except Exception as e:
        import traceback
        logger.error(f"Upload Error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/history')
def history():
    """显示历史批改记录"""
    history_items = []
    
    try:
        # 扫描上传目录中的所有 grading_*.json 文件
        files = os.listdir(Config.UPLOAD_FOLDER)
        json_files = [f for f in files if f.startswith('grading_') and f.endswith('.json')]
        
        # 按修改时间倒序排列
        json_files.sort(key=lambda x: os.path.getmtime(os.path.join(Config.UPLOAD_FOLDER, x)), reverse=True)
        
        for json_file in json_files:
            try:
                file_path = os.path.join(Config.UPLOAD_FOLDER, json_file)
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path)))
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                final_results = data.get('final_results', {})
                image_path = data.get('image_path', '')
                marked_image_path = data.get('marked_image_path', '')
                
                # 尝试从路径中提取文件名
                original_filename = os.path.basename(image_path)
                marked_filename = os.path.basename(marked_image_path) if marked_image_path else original_filename
                
                # 如果 marked_image_filename 字段存在，优先使用
                if 'marked_image_filename' in data:
                    marked_filename = data['marked_image_filename']
                
                # 检查图片文件是否存在
                if not os.path.exists(os.path.join(Config.UPLOAD_FOLDER, marked_filename)):
                    # 如果标记图不存在，尝试原图
                    if os.path.exists(os.path.join(Config.UPLOAD_FOLDER, original_filename)):
                        marked_filename = original_filename
                    else:
                        # 图片都不存在，可能被清理了，跳过
                        continue

                history_items.append({
                    'original_filename': original_filename,
                    'image_filename': marked_filename,
                    'timestamp': timestamp,
                    'total_score': final_results.get('total_score', 0),
                    'max_total_score': final_results.get('max_total_score', 0),
                    'accuracy': final_results.get('accuracy', 0)
                })
            except Exception as e:
                logger.warning(f"Error parsing history item {json_file}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error listing history: {e}")
        flash(f"获取历史记录失败: {str(e)}")
        
    return render_template('history.html', history_items=history_items)

@bp.route('/delete_history', methods=['POST'])
def delete_history():
    """删除选中的历史记录"""
    try:
        data = request.get_json()
        filenames = data.get('filenames', [])
        
        if not filenames:
            return jsonify({'success': False, 'error': '未选择任何记录'})
            
        deleted_count = 0
        errors = []
        
        for filename in filenames:
            try:
                base_name = os.path.splitext(filename)[0]
                
                # 需要删除的文件列表
                files_to_delete = [
                    # 原始图片
                    os.path.join(Config.UPLOAD_FOLDER, filename),
                    # 批改报告 JSON
                    os.path.join(Config.UPLOAD_FOLDER, f"grading_{base_name}.json"),
                    # Word 报告
                    os.path.join(Config.UPLOAD_FOLDER, f"report_{base_name}.docx"),
                ]
                
                # 尝试查找可能的标记图片
                for ext in ['.jpg', '.png', '.jpeg']:
                     files_to_delete.append(os.path.join(Config.UPLOAD_FOLDER, f"marked_{base_name}{ext}"))
                
                # 还要删除 static/grading/{base_name} 目录
                grading_dir = os.path.join(Config.GRADING_FOLDER, base_name)
                if os.path.exists(grading_dir):
                    shutil.rmtree(grading_dir)
                
                # 执行文件删除
                for f_path in files_to_delete:
                    if os.path.exists(f_path):
                        os.remove(f_path)
                
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"删除 {filename} 失败: {str(e)}")
        
        if errors:
            return jsonify({'success': True, 'message': f"成功删除 {deleted_count} 条记录，{len(errors)} 条失败", 'errors': errors})
        else:
            return jsonify({'success': True, 'message': f"成功删除 {deleted_count} 条记录"})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/clear_history', methods=['POST'])
def clear_history():
    """清空所有历史记录"""
    try:
        # 清空上传目录
        if os.path.exists(Config.UPLOAD_FOLDER):
            shutil.rmtree(Config.UPLOAD_FOLDER)
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
            
        # 清空批改目录
        if os.path.exists(Config.GRADING_FOLDER):
            shutil.rmtree(Config.GRADING_FOLDER)
            os.makedirs(Config.GRADING_FOLDER, exist_ok=True)
            
        # 清空内存中的任务状态
        grading_tasks.clear()
        
        flash("所有历史记录已清空")
    except Exception as e:
        flash(f"清空失败: {str(e)}")
        
    return redirect(url_for('main.history'))

@bp.route('/download_report_word/<filename>')
def download_word_report(filename):
    """下载Word格式报告"""
    try:
        # 1. 找到JSON报告
        json_filename = f"grading_{os.path.splitext(filename)[0]}.json"
        report_path = os.path.join(Config.UPLOAD_FOLDER, json_filename)
        
        if not os.path.exists(report_path):
            flash("找不到批改报告数据")
            return redirect(url_for('main.index'))
            
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
            
        # 2. 生成Word报告
        output_filename = f"report_{os.path.splitext(filename)[0]}.docx"
        output_path = os.path.join(Config.UPLOAD_FOLDER, output_filename)
        
        generator = ReportGenerator()
        generator.generate_word_report(report_data, output_path)
        
        # 3. 发送文件
        return send_file(output_path, as_attachment=True, download_name=output_filename)
        
    except Exception as e:
        import traceback
        logger.error(f"Generate Report Error: {traceback.format_exc()}")
        flash(f"生成Word报告失败: {str(e)}")
        return redirect(url_for('main.view_report', filename=filename))

@bp.route('/report/<filename>')
def view_report(filename):
    """显示批改报告"""
    try:
        # 确保文件名安全
        filename = secure_filename(filename)
        base_name = os.path.splitext(filename)[0]
        json_filename = f"grading_{base_name}.json"
        report_path = os.path.join(Config.UPLOAD_FOLDER, json_filename)
        
        if not os.path.exists(report_path):
            logger.warning(f"Report file not found: {report_path}")
            flash("找不到批改报告")
            return redirect(url_for('main.index'))
            
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
            
        # 将 model_results 注入到 final_results 中
        grading_data = report['final_results']
        grading_data['model_results'] = report.get('model_results', {})
        
        # 确定使用哪张图片（优先使用标记后的图片）
        image_filename = report.get('marked_image_filename', filename)
        # 如果标记图片不存在（可能是旧报告），回退到原图
        if not os.path.exists(os.path.join(Config.UPLOAD_FOLDER, image_filename)):
            image_filename = filename
            
        return render_template('result.html',
                               grading=grading_data,
                               image_url=url_for('static', filename=f'uploads/{image_filename}'),
                               report_url=url_for('static', filename=f'uploads/grading_{os.path.splitext(filename)[0]}.json'),
                               original_filename=filename)
                               
    except Exception as e:
        flash(f"加载报告失败: {str(e)}")
        return redirect(url_for('main.index'))

@bp.route('/analyze', methods=['POST'])
def analyze_exam():
    """仅分析试卷，不批改"""
    try:
        if 'exam_image' not in request.files:
            flash('未找到文件部分')
            return redirect(request.url)
        
        file = request.files['exam_image']
        
        if file.filename == '':
            flash('未选择文件')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            flash(f"试卷上传成功: {filename}")
            return redirect(url_for('main.index'))
            
    except Exception as e:
        import traceback
        logger.critical(f"Critical Error: {traceback.format_exc()}")
        flash(f"系统严重错误: {str(e)}")
        return redirect(url_for('main.index'))
