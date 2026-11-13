###############################################################################
# 08-freemarker-memshell —— 多阶段构建
#   构建阶段：maven:3.6.3-jdk-8（本地已有镜像，避免大体积拉取）
#   运行阶段：eclipse-temurin:8-jre-alpine + iptables
###############################################################################

# --------------------------------------------------------------------------
# Stage 1: build
# --------------------------------------------------------------------------
FROM maven:3.6.3-jdk-8 AS build
WORKDIR /build

# 先把源码和 pom 一起拷进来解依赖。
# 注意：不要把 dependency:go-offline 单独放在 COPY src 之前 —— 它对
# spring-boot-starter-* 这类 BOM 管理的依赖解析结果不可靠，实测编译阶段会缺 jar。
COPY pom.xml .
COPY src ./src
RUN mvn -B -q dependency:resolve-plugins dependency:resolve dependency:resolve \
 && mvn -B -q package -DskipTests \
 && cp target/themepreview-1.0.0.jar /build/app.jar

# --------------------------------------------------------------------------
# Stage 2: runtime
# --------------------------------------------------------------------------
FROM eclipse-temurin:8-jre-alpine

# iptables 用于切断出网（NET_ADMIN 由 compose 提供）
RUN apk add --no-cache iptables bash tzdata

ENV TZ=Asia/Shanghai \
    JAVA_OPTS="-Xms64m -Xmx256m -Dfile.encoding=UTF-8"

WORKDIR /app
COPY --from=build /build/app.jar /app/app.jar
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 注意：/flag 绝不在这里创建 —— 由 entrypoint.sh 在容器启动时写入，
#       保证 flag 不会进入任何镜像层。
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
