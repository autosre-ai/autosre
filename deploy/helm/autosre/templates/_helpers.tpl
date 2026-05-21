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
Agent labels
*/}}
{{- define "autosre.agent.labels" -}}
{{ include "autosre.labels" . }}
app.kubernetes.io/component: agent
{{- end }}

{{/*
Agent selector labels
*/}}
{{- define "autosre.agent.selectorLabels" -}}
{{ include "autosre.selectorLabels" . }}
app.kubernetes.io/component: agent
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
Web labels
*/}}
{{- define "autosre.web.labels" -}}
{{ include "autosre.labels" . }}
app.kubernetes.io/component: web
{{- end }}

{{/*
Web selector labels
*/}}
{{- define "autosre.web.selectorLabels" -}}
{{ include "autosre.selectorLabels" . }}
app.kubernetes.io/component: web
{{- end }}

{{/*
Config (LiteLLM) labels
*/}}
{{- define "autosre.config.labels" -}}
{{ include "autosre.labels" . }}
app.kubernetes.io/component: config
{{- end }}

{{/*
Config selector labels
*/}}
{{- define "autosre.config.selectorLabels" -}}
{{ include "autosre.selectorLabels" . }}
app.kubernetes.io/component: config
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "autosre.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "autosre.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Secret name
*/}}
{{- define "autosre.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- include "autosre.fullname" . }}
{{- end }}
{{- end }}

{{/*
PostgreSQL connection string
*/}}
{{- define "autosre.postgresql.host" -}}
{{- if .Values.externalPostgresql.enabled }}
{{- .Values.externalPostgresql.host }}
{{- else if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" .Release.Name }}
{{- else }}
{{- fail "Either postgresql.enabled or externalPostgresql.enabled must be true" }}
{{- end }}
{{- end }}

{{- define "autosre.postgresql.port" -}}
{{- if .Values.externalPostgresql.enabled }}
{{- .Values.externalPostgresql.port }}
{{- else }}
{{- 5432 }}
{{- end }}
{{- end }}

{{/*
Redis connection string
*/}}
{{- define "autosre.redis.host" -}}
{{- if .Values.externalRedis.enabled }}
{{- .Values.externalRedis.host }}
{{- else if .Values.redis.enabled }}
{{- printf "%s-redis-master" .Release.Name }}
{{- else }}
{{- fail "Either redis.enabled or externalRedis.enabled must be true" }}
{{- end }}
{{- end }}

{{- define "autosre.redis.port" -}}
{{- if .Values.externalRedis.enabled }}
{{- .Values.externalRedis.port }}
{{- else }}
{{- 6379 }}
{{- end }}
{{- end }}

{{/*
Neo4j connection string
*/}}
{{- define "autosre.neo4j.uri" -}}
{{- if .Values.externalNeo4j.enabled }}
{{- .Values.externalNeo4j.uri }}
{{- else if .Values.neo4j.enabled }}
{{- printf "bolt://%s-neo4j:7687" .Release.Name }}
{{- else }}
{{- fail "Either neo4j.enabled or externalNeo4j.enabled must be true" }}
{{- end }}
{{- end }}

{{/*
Image helpers
*/}}
{{- define "autosre.agent.image" -}}
{{- printf "%s:%s" .Values.agent.image.repository (default .Chart.AppVersion .Values.agent.image.tag) }}
{{- end }}

{{- define "autosre.api.image" -}}
{{- printf "%s:%s" .Values.api.image.repository (default .Chart.AppVersion .Values.api.image.tag) }}
{{- end }}

{{- define "autosre.web.image" -}}
{{- printf "%s:%s" .Values.web.image.repository (default .Chart.AppVersion .Values.web.image.tag) }}
{{- end }}

{{- define "autosre.config.image" -}}
{{- printf "%s:%s" .Values.config.image.repository .Values.config.image.tag }}
{{- end }}

{{/*
Service URLs
*/}}
{{- define "autosre.agent.url" -}}
{{- printf "http://%s-agent:%d" (include "autosre.fullname" .) (.Values.agent.service.port | int) }}
{{- end }}

{{- define "autosre.api.url" -}}
{{- printf "http://%s-api:%d" (include "autosre.fullname" .) (.Values.api.service.port | int) }}
{{- end }}

{{- define "autosre.config.url" -}}
{{- printf "http://%s-config:%d" (include "autosre.fullname" .) (.Values.config.service.port | int) }}
{{- end }}

{{/*
Annotations helper
*/}}
{{- define "autosre.annotations" -}}
{{- with .Values.commonAnnotations }}
{{ toYaml . }}
{{- end }}
{{- end }}
