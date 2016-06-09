import django
from django.http import HttpResponse, Http404
from django.utils.http import urlquote
import os
import re
import mimetypes

from . settings import LASANA_USE_X_SENDFILE, LASANA_NGINX_ACCEL_REDIRECT_BASE_URL

#For no-XSendfile approach
if django.VERSION >= (1, 9):
    from wsgiref.util import FileWrapper
else:
    from django.core.servers.basehttp import FileWrapper

CONTENT_RANGE_REGEXP = re.compile(r"bytes=(\d+)?-(\d+)?")

def send(request, file):
    if not file:
        raise Http404

    detected_type = mimetypes.guess_type(file.path)[0]
    if detected_type is None:
        detected_type = 'application/octet-stream'

    if LASANA_USE_X_SENDFILE:
        response = HttpResponse(content_type=detected_type)
        response['Content-Disposition'] = 'filename=%s' % urlquote(os.path.basename(file.name))
        content_range = request.META.get('HTTP_RANGE')
        range_begin = None
        range_end = None
        if content_range is not None:
            match = CONTENT_RANGE_REGEXP.match(content_range)
            if match is not None:
                range_begin, range_end = match.groups()
                range_begin = int(range_begin) if range_begin is not None else None
                range_end = int(range_end) if range_end is not None else None
                if (range_begin is None or range_begin < file.size) and (range_end is None or range_end < file.size):
                    # Use 206 Partial Content
                    response.status_code = 206
                    response['Content-Range'] = "bytes %s-%s/%d" % (range_begin if range_begin is not None else "0",
                                                                    range_end if range_end is not None else (file.size - 1), file.size)
                else:
                    # Throw 416 Range Not Satisfiable
                    return HttpResponse(status=416)

        if LASANA_USE_X_SENDFILE == 'lighttpd':
            response['X-Sendfile2'] = "%s %s-%s" % (urlquote(file.path), str(range_begin) if range_begin is not None else "0",
                                                                         str(range_end) if range_end is not None else "")
        elif LASANA_USE_X_SENDFILE == 'nginx':
            response['X-Accel-Redirect'] = (LASANA_NGINX_ACCEL_REDIRECT_BASE_URL + os.path.basename(file.name)).encode('UTF-8')
        else:
            raise RuntimeError('LASANA_USE_X_SENDFILE must be "lighttpd" or "nginx".')

        return response
    else:
        response = HttpResponse(FileWrapper(file), content_type=detected_type)
        response['Content-Disposition'] = 'filename=%s' % urlquote(os.path.basename(file.name))
        response['Content-Length'] = file.size
        return response
