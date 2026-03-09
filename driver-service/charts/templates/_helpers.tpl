{{- define "driver-service.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "driver-service.labels" -}}
app: {{ include "driver-service.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
