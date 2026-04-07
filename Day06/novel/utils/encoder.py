import json


class MyEncoder(json.JSONEncoder):
    """JSON 编码：支持 bytes；若已安装 numpy，则支持 ndarray。"""

    def default(self, obj):
        if isinstance(obj, bytes):
            return str(obj, encoding="utf-8")
        try:
            import numpy as np

            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return json.JSONEncoder.default(self, obj)
