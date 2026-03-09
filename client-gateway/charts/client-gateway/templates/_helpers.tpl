{{/*
Expand the name of the chart.
*/}}
{{- define "client-gateway.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "client-gateway.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "client-gateway.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "client-gateway.labels" -}}
helm.sh/chart: {{ include "client-gateway.chart" . }}
{{ include "client-gateway.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Selector labels
*/}}
{{- define "client-gateway.selectorLabels" -}}
app: client-gateway
app.kubernetes.io/name: {{ include "client-gateway.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "client-gateway.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "client-gateway.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
AWS Account ID
*/}}
{{- define "client-gateway.awsAccountId" -}}
{{- required "A valid .Values.aws.accountId is required!" .Values.aws.accountId -}}
{{- end }}

{{/*
Image name
*/}}
{{- define "client-gateway.image" -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- $_ := include "client-gateway.awsAccountId" . -}}
{{- $repository := tpl .Values.image.repository . -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end }}

{{/*
Service Account Role ARN
*/}}
{{- define "client-gateway.roleArn" -}}
{{- if .Values.serviceAccount.roleArn -}}
{{- $_ := include "client-gateway.awsAccountId" . -}}
{{- tpl .Values.serviceAccount.roleArn . -}}
{{- end -}}
{{- end }}
