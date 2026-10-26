from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Custom exception handler to provide clean and descriptive error
    messages for mobile (Flutter) applications.
    """
    response = exception_handler(exc, context)

    if response is not None and isinstance(response.data, dict):
        if "detail" not in response.data:
            first_err = None
            for key, val in response.data.items():
                if isinstance(val, list) and len(val) > 0:
                    first_err = f"{key}: {val[0]}"
                    break
                elif isinstance(val, str):
                    first_err = f"{key}: {val}"
                    break
            if first_err:
                response.data["detail"] = first_err

    return response
