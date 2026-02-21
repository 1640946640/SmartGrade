from flask import Blueprint, jsonify
from app.services.grading_service import ExamGrader, grading_tasks

bp = Blueprint('api', __name__)

@bp.route('/api/models')
def get_models():
    """获取可用模型列表"""
    try:
        grader = ExamGrader()
        models = grader.check_available_models()
        return jsonify({'success': True, 'models': models})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/progress/<task_id>')
def get_progress(task_id):
    """获取任务进度"""
    task = grading_tasks.get(task_id)
    if not task:
        return jsonify({'success': False, 'error': '任务不存在'})
    return jsonify(task)
