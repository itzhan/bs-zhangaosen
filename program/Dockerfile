# ============================================================
# 京东手机评论分析系统 — Docker 镜像
# Python 3.10 + JDK 11 + Hadoop Client + PySpark
# ============================================================
FROM python:3.10-slim

# 中文编码支持
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1

# 设置 pip 国内镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 代理支持（可选，通过 docker compose build --build-arg 传入）
ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy=${HTTP_PROXY} https_proxy=${HTTPS_PROXY}

# 安装 JDK + 工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk \
    procps \
    curl \
    wget \
    ssh \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH=$JAVA_HOME/bin:$PATH

# ---- 安装 Hadoop 客户端 ----
ENV HADOOP_VERSION=3.2.1
ENV HADOOP_HOME=/opt/hadoop
ENV HADOOP_CONF_DIR=/app/hadoop-conf
ENV PATH=$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH

# 使用本地预下载的 Hadoop（避免构建时下载 350MB）
COPY hadoop-3.2.1.tar.gz /tmp/hadoop-3.2.1.tar.gz
RUN tar -xzf /tmp/hadoop-3.2.1.tar.gz -C /opt/ \
    && mv /opt/hadoop-3.2.1 ${HADOOP_HOME} \
    && rm /tmp/hadoop-3.2.1.tar.gz \
    && rm -rf ${HADOOP_HOME}/share/doc

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建 Hadoop 配置目录（指向 HDFS NameNode）
RUN mkdir -p /app/hadoop-conf && \
    echo '<?xml version="1.0" encoding="UTF-8"?>' > /app/hadoop-conf/core-site.xml && \
    echo '<configuration>' >> /app/hadoop-conf/core-site.xml && \
    echo '  <property><name>fs.defaultFS</name><value>hdfs://namenode:9000</value></property>' >> /app/hadoop-conf/core-site.xml && \
    echo '</configuration>' >> /app/hadoop-conf/core-site.xml && \
    echo '<?xml version="1.0" encoding="UTF-8"?>' > /app/hadoop-conf/hdfs-site.xml && \
    echo '<configuration>' >> /app/hadoop-conf/hdfs-site.xml && \
    echo '  <property><name>dfs.replication</name><value>1</value></property>' >> /app/hadoop-conf/hdfs-site.xml && \
    echo '  <property><name>dfs.client.use.datanode.hostname</name><value>true</value></property>' >> /app/hadoop-conf/hdfs-site.xml && \
    echo '</configuration>' >> /app/hadoop-conf/hdfs-site.xml

# 安装 MySQL JDBC 驱动到 PySpark jars 目录（使用本地预下载文件，避免构建时网络问题）
COPY mysql-connector-j-8.0.33.jar /tmp/mysql-connector-j-8.0.33.jar
RUN PYSPARK_JARS=$(python -c "import pyspark,os; print(os.path.join(os.path.dirname(pyspark.__file__),'jars'))") && \
    cp /tmp/mysql-connector-j-8.0.33.jar "$PYSPARK_JARS/mysql-connector-j-8.0.33.jar" && \
    rm /tmp/mysql-connector-j-8.0.33.jar && \
    echo "MySQL JDBC driver installed to: $PYSPARK_JARS"

# 创建必要目录
RUN mkdir -p output/sentiment_batch output/spark_results models .logs

# 暴露端口
EXPOSE 5001

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5001/ || exit 1

CMD ["python", "run.py"]
