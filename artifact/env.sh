# Build environment. Supply JAVA_HOME and ANDROID_HOME for a clean extraction.
# The sibling shared SDK is only a workspace fallback, never included in the artifact.
RESIDUE_ARTIFACT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ -z "${ANDROID_HOME:-}" ]; then
  export ANDROID_HOME="$RESIDUE_ARTIFACT_DIR/../../shared-android/sdk"
fi
if [ -z "${JAVA_HOME:-}" ]; then
  if [ -x /usr/libexec/java_home ]; then export JAVA_HOME=$(/usr/libexec/java_home -v 17)
  else export JAVA_HOME="$(dirname "$(dirname "$(command -v javac)")")"; fi
fi
export ANDROID_SDK_ROOT="$ANDROID_HOME"
