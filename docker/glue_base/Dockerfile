FROM python:3.7-stretch


# 新代码
COPY ./requirements.txt /tmp

RUN pip3 install pip --upgrade --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple \
 && pip3 install --no-cache-dir -r /tmp/requirements.txt -i https://mirrors.aliyun.com/pypi/simple


CMD [""]
