from __future__ import annotations

from flask import jsonify

from . import strategic_tasks_bp
from ..services.strategic_tasks_feishu import StrategicTaskFeishuError, read_strategic_tasks


@strategic_tasks_bp.get('/strategic-tasks')
def get_strategic_tasks():
    try:
        payload = read_strategic_tasks()
    except StrategicTaskFeishuError as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(exc),
                    "data": {
                        "source": "unavailable",
                        "record_count": 0,
                        "records": [],
                    },
                }
            ),
            503,
        )

    return jsonify({"success": True, "data": payload})
