pipeline {
  agent any
  options {
    disableConcurrentBuilds()
    timestamps()
  }
  environment {
    IMAGE_REPOSITORY = 'wenyou7/open-webui'
    DOCKERHUB_CREDENTIALS = 'dockerhub-token'
    TARGET_BRANCH = 'dev'
    DOCKER_BUILDKIT = '1'
  }
  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script {
          def currentBranch = env.BRANCH_NAME
          if (!currentBranch && env.GIT_BRANCH) {
            currentBranch = env.GIT_BRANCH.replaceFirst(/^origin\//, '')
          }
          if (!currentBranch) {
            currentBranch = sh(
              script: 'git symbolic-ref --short -q HEAD || true',
              returnStdout: true
            ).trim()
          }
          if (currentBranch && currentBranch != env.TARGET_BRANCH) {
            error("仅允许 ${env.TARGET_BRANCH} 分支发布，当前分支：${currentBranch}")
          }

          env.GIT_SHA = sh(
            script: 'git rev-parse --short=12 HEAD',
            returnStdout: true
          ).trim()
          def buildTime = sh(
            script: 'TZ=Asia/Shanghai date +%Y%m%d%H%M%S',
            returnStdout: true
          ).trim()
          env.IMAGE_VERSION = "${buildTime}-b${env.BUILD_NUMBER}"
        }
        echo "Image version: ${env.IMAGE_VERSION}"
        echo "Git commit: ${env.GIT_SHA}"
      }
    }
    stage('Build') {
      steps {
        retry(3) {
          sh '''
            docker build --pull \
              --build-arg BUILD_HASH="$GIT_SHA" \
              --tag "$IMAGE_REPOSITORY:$IMAGE_VERSION" \
              --tag "$IMAGE_REPOSITORY:latest" \
              .
          '''
        }
      }
    }
    stage('Push') {
      steps {
        script {
          retry(3) {
            docker.withRegistry('https://index.docker.io/v1/', DOCKERHUB_CREDENTIALS) {
              sh '''
                push_with_retry() {
                  image="$1"
                  attempt=1
                  max_attempts=5
                  while true; do
                    echo "Pushing $image (attempt $attempt/$max_attempts)"
                    if docker push "$image"; then
                      echo "Push succeeded: $image"
                      return 0
                    fi
                    if [ "$attempt" -ge "$max_attempts" ]; then
                      echo "Push failed after $max_attempts attempts: $image"
                      return 1
                    fi
                    delay=$((attempt * 15))
                    echo "Push failed; retrying in ${delay}s..."
                    sleep "$delay"
                    attempt=$((attempt + 1))
                  done
                }
                push_with_retry "$IMAGE_REPOSITORY:$IMAGE_VERSION"
                push_with_retry "$IMAGE_REPOSITORY:latest"
              '''
            }
          }
        }
      }
    }
  }
  post {
    success {
      // ================== 自动化部署 ==================
      sh '''
        echo "触发 Watchtower 拉取新镜像并重启服务..."
        curl -H "Authorization: Bearer a3360059" http://95.41.67.11:8081/v1/update
      '''

      // 部署完成后发送成功通知
      sh '''
        curl --fail --silent --show-error --get \
          --connect-timeout 5 \
          --max-time 15 \
          --data-urlencode "t=部署成功：$IMAGE_REPOSITORY:$IMAGE_VERSION" \
          --data-urlencode "m=镜像：$IMAGE_REPOSITORY:$IMAGE_VERSION，Git：$GIT_SHA，已完成镜像推送与容器热更！" \
          'http://192.168.100.153:9997/n/t' \
          || echo 'Image notification failed; image publishing remains successful.'
      '''
    }
    always {
      sh 'docker image prune --force || true'
    }
  }
}
