from rest_framework.renderers import JSONRenderer


class EnvelopedJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return super().render(data, accepted_media_type, renderer_context)

        response = renderer_context.get("response") if renderer_context else None
        if isinstance(data, dict) and {"success", "data", "errors"}.intersection(data.keys()):
            return super().render(data, accepted_media_type, renderer_context)

        status_code = getattr(response, "status_code", 200)
        is_error = status_code >= 400
        if is_error:
            payload = {"success": False, "data": None, "errors": data}
        else:
            meta = data.get("meta") if isinstance(data, dict) else None
            body = data.get("results") if isinstance(data, dict) and "results" in data else data
            payload = {"success": True, "data": body, "errors": None}
            if meta is not None:
                payload["meta"] = meta
        return super().render(payload, accepted_media_type, renderer_context)
