FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    apache2 \
    libapache2-mod-wsgi-py3 \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 將 Apache log 導向 Docker stdout/stderr
RUN ln -sf /dev/stdout /var/log/apache2/access.log \
 && ln -sf /dev/stderr /var/log/apache2/error.log

# 啟用 mod_wsgi
RUN a2enmod wsgi

# 安裝 Python 套件
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Apache VirtualHost 設定
COPY apache/app.conf /etc/apache2/sites-available/app.conf
RUN a2dissite 000-default.conf && a2ensite app.conf

# 複製應用程式
COPY app/ /var/www/app/
COPY frontend/ /var/www/app/frontend/

RUN chown -R www-data:www-data /var/www/app

EXPOSE 80

CMD ["apache2ctl", "-D", "FOREGROUND"]
