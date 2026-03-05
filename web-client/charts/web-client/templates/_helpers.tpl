{{/*
Expand the name of the chart.
*/}}
{{- define "web-client.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "web-client.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart label.
*/}}
{{- define "web-client.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels — applied to every resource.
*/}}
{{- define "web-client.labels" -}}
helm.sh/chart: {{ include "web-client.chart" . }}
{{ include "web-client.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
team: {{ .Values.labels.team }}
env: {{ .Values.labels.env }}
service: {{ .Values.labels.service }}
{{- end }}

{{/*
Selector labels — used by Deployment selector and Service selector.
*/}}
{{- define "web-client.selectorLabels" -}}
app.kubernetes.io/name: {{ include "web-client.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
