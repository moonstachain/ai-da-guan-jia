from __future__ import annotations

from flask import jsonify, request

from . import smart_youth_bp
from ..services.smart_youth_feishu import SmartYouthFeishuError, capabilities_meta, search_capability_records


@smart_youth_bp.get("/meta")
def get_meta():
    try:
        return jsonify({"success": True, "data": capabilities_meta()})
    except SmartYouthFeishuError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503


@smart_youth_bp.get("/capabilities")
def list_capabilities():
    try:
        return jsonify({"success": True, "data": capabilities_meta()})
    except SmartYouthFeishuError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503


@smart_youth_bp.post("/capabilities/<capability_id>/searchRecords")
def search_records(capability_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        data = search_capability_records(capability_id, payload)
        return jsonify({"success": True, "data": data})
    except SmartYouthFeishuError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
