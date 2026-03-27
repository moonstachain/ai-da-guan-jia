"""
API路由模块
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
strategic_tasks_bp = Blueprint('strategic_tasks', __name__)
smart_youth_bp = Blueprint('smart_youth', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import strategic_tasks  # noqa: E402, F401
from . import smart_youth  # noqa: E402, F401
