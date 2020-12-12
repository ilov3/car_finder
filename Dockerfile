FROM python:3.7

ENV PYTHONUNBUFFERED=1
ADD requirements.txt .
RUN pip install -r requirements.txt

COPY . ./app
WORKDIR ./app
EXPOSE 6800
RUN chmod a+x ./start.sh
CMD ["./start.sh"]