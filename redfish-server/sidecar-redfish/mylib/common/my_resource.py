from flask import request
from flask_restx import Resource
from functools import wraps

class MyResource(Resource):
    """
    自定義一個class MyResource(Resource):
    讓所有的MyRouter繼承MyResource
    並且，當MyRouter實作`def get()`方法時，可以先做validate再實作原來的get()內容

    為什麼不使用flask restx的validation呢？
    """

    def dispatch_request(self, *args, **kwargs):
        """
        Override Resource.dispatch_request to inject validation logic.
        This is called before calling get/post/etc.
        """
        # def wrapper(*args, **kwargs):
        #     self._validate_request()  # 自訂驗證邏輯
        #     return super().dispatch_request(*args, **kwargs)
        # return wrapper(*args, **kwargs)
        
        self._validate_request()  # 自訂驗證邏輯
        return super().dispatch_request(*args, **kwargs)

    def _validate_request(self):
        raise NotImplementedError
