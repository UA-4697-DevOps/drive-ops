{{- define "client-gateway.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "client-gateway.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "client-gateway.labels" -}}
app: {{ include "client-gateway.name" . }}
app.kubernetes.io/name: {{ include "client-gateway.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "client-gateway.selectorLabels" -}}
app: {{ include "client-gateway.name" . }}
app.kubernetes.io/name: {{ include "client-gateway.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
