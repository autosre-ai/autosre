{{/*
Expand the name of the chart.
*/}}
{{- define "autosre.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "autosre.fullname" -}}
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
{{- define "autosre.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "autosre.labels" -}}
helm.sh/chart: {{ include "autosre.chart" . }}
{{ include "autosre.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "autosre.selectorLabels" -}}
app.kubernetes.io/name: {{ include "autosre.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
API labels
*/}}
{{- define "autosre.api.labels" -}}
{{ include "autosre.labels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
API selector labels
*/}}
{{- define "autosre.api.selectorLabels" -}}
{{ include "autosre.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
UI labels
*/}}
{{- define "autosre.ui.labels" -}}
{{ include "autosre.labels" . }}
app.kubernetes.io/component: ui
{{- end }}

{{/*
UI selector labels
*/}}
{{- define "autosre.ui.selectorLabels" -}}
{{ include "autosre.selectorLabels" . }}
app.kubernetes.io/component: ui
{{- end }}

{{/*
Create the name of the service account to use for API
*/}}
{{- define "autosre.api.serviceAccountName" -}}
{{- if .Values.api.serviceAccount.create }}
{{- default (printf "%s-api" (include "autosre.fullname" .)) .Values.api.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.api.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
API image
*/}}
{{- define "autosre.api.image" -}}
{{- $tag := .Values.api.image.tag | default .Chart.AppVersion }}
{{- printf "%s:%s" .Values.api.image.repository $tag }}
{{- end }}

{{/*
UI image
*/}}
{{- define "autosre.ui.image" -}}
{{- $tag := .Values.ui.image.tag | default .Chart.AppVersion }}
{{- printf "%s:%s" .Values.ui.image.repository $tag }}
{{- end }}

{{/*
PostgreSQL host
*/}}
{{- define "autosre.postgresql.host" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "autosre.fullname" .) }}
{{- else }}
{{- .Values.externalPostgresql.host }}
{{- end }}
{{- end }}

{{/*
PostgreSQL port
*/}}
{{- define "autosre.postgresql.port" -}}
{{- if .Values.postgresql.enabled -}}
5432
{{- else -}}
{{- .Values.externalPostgresql.port -}}
{{- end -}}
{{- end }}

{{/*
PostgreSQL database
*/}}
{{- define "autosre.postgresql.database" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.database }}
{{- else }}
{{- .Values.externalPostgresql.database }}
{{- end }}
{{- end }}

{{/*
PostgreSQL username
*/}}
{{- define "autosre.postgresql.username" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.username }}
{{- else }}
{{- .Values.externalPostgresql.username }}
{{- end }}
{{- end }}

{{/*
PostgreSQL secret name
*/}}
{{- define "autosre.postgresql.secretName" -}}
{{- if .Values.postgresql.enabled }}
{{- if .Values.postgresql.auth.existingSecret }}
{{- .Values.postgresql.auth.existingSecret }}
{{- else }}
{{- printf "%s-postgresql" (include "autosre.fullname" .) }}
{{- end }}
{{- else }}
{{- if .Values.externalPostgresql.existingSecret }}
{{- .Values.externalPostgresql.existingSecret }}
{{- else }}
{{- printf "%s-external-postgresql" (include "autosre.fullname" .) }}
{{- end }}
{{- end }}
{{- end }}

{{/*
PostgreSQL secret key
*/}}
{{- define "autosre.postgresql.secretKey" -}}
{{- if .Values.postgresql.enabled -}}
password
{{- else -}}
postgresql-password
{{- end -}}
{{- end }}

{{/*
Redis host
*/}}
{{- define "autosre.redis.host" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" (include "autosre.fullname" .) }}
{{- else }}
{{- .Values.externalRedis.host }}
{{- end }}
{{- end }}

{{/*
Redis port
*/}}
{{- define "autosre.redis.port" -}}
{{- if .Values.redis.enabled -}}
6379
{{- else -}}
{{- .Values.externalRedis.port -}}
{{- end -}}
{{- end }}

{{/*
Redis secret name
*/}}
{{- define "autosre.redis.secretName" -}}
{{- if .Values.redis.enabled }}
{{- if .Values.redis.auth.existingSecret }}
{{- .Values.redis.auth.existingSecret }}
{{- else }}
{{- printf "%s-redis" (include "autosre.fullname" .) }}
{{- end }}
{{- else }}
{{- if .Values.externalRedis.existingSecret }}
{{- .Values.externalRedis.existingSecret }}
{{- else }}
{{- printf "%s-external-redis" (include "autosre.fullname" .) }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Redis secret key
*/}}
{{- define "autosre.redis.secretKey" -}}
redis-password
{{- end }}

{{/*
Secrets name
*/}}
{{- define "autosre.secretsName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "autosre.fullname" .) }}
{{- end }}
{{- end }}

{{/*
ConfigMap name
*/}}
{{- define "autosre.configMapName" -}}
{{- printf "%s-config" (include "autosre.fullname" .) }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "autosre.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Common annotations
*/}}
{{- define "autosre.annotations" -}}
{{- with .Values.commonAnnotations }}
{{ toYaml . }}
{{- end }}
{{- end }}
