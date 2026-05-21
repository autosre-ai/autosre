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
Create the name of the secret
*/}}
{{- define "autosre.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- include "autosre.fullname" . }}
{{- end }}
{{- end }}

{{/*
Create the name of the configmap
*/}}
{{- define "autosre.configMapName" -}}
{{- include "autosre.fullname" . }}-config
{{- end }}

{{/*
Agent fullname
*/}}
{{- define "autosre.agent.fullname" -}}
{{- include "autosre.fullname" . }}-agent
{{- end }}

{{/*
API fullname
*/}}
{{- define "autosre.api.fullname" -}}
{{- include "autosre.fullname" . }}-api
{{- end }}

{{/*
Web fullname
*/}}
{{- define "autosre.web.fullname" -}}
{{- include "autosre.fullname" . }}-web
{{- end }}

{{/*
Return the proper image name
*/}}
{{- define "autosre.image" -}}
{{- $registryName := .registry -}}
{{- $repositoryName := .repository -}}
{{- $tag := .tag | default $.Chart.AppVersion -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag }}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag }}
{{- end }}
{{- end }}

{{/*
Return the proper agent image name
*/}}
{{- define "autosre.agent.image" -}}
{{- $imageRoot := .Values.agent.image -}}
{{- $tag := .Values.agent.image.tag | default .Chart.AppVersion -}}
{{- printf "%s:%s" $imageRoot.repository $tag }}
{{- end }}

{{/*
Return the proper API image name
*/}}
{{- define "autosre.api.image" -}}
{{- $imageRoot := .Values.api.image -}}
{{- $tag := .Values.api.image.tag | default .Chart.AppVersion -}}
{{- printf "%s:%s" $imageRoot.repository $tag }}
{{- end }}

{{/*
Return the proper web image name
*/}}
{{- define "autosre.web.image" -}}
{{- $imageRoot := .Values.web.image -}}
{{- $tag := .Values.web.image.tag | default .Chart.AppVersion -}}
{{- printf "%s:%s" $imageRoot.repository $tag }}
{{- end }}

{{/*
Return PostgreSQL host
*/}}
{{- define "autosre.postgresql.host" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "autosre.fullname" .) }}
{{- else }}
{{- .Values.externalDatabase.host }}
{{- end }}
{{- end }}

{{/*
Return PostgreSQL port
*/}}
{{- define "autosre.postgresql.port" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "5432" }}
{{- else }}
{{- .Values.externalDatabase.port | toString }}
{{- end }}
{{- end }}

{{/*
Return PostgreSQL database
*/}}
{{- define "autosre.postgresql.database" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.database }}
{{- else }}
{{- .Values.externalDatabase.database }}
{{- end }}
{{- end }}

{{/*
Return PostgreSQL username
*/}}
{{- define "autosre.postgresql.username" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.username }}
{{- else }}
{{- .Values.externalDatabase.username }}
{{- end }}
{{- end }}

{{/*
Return PostgreSQL secret name
*/}}
{{- define "autosre.postgresql.secretName" -}}
{{- if .Values.postgresql.enabled }}
{{- if .Values.postgresql.auth.existingSecret }}
{{- .Values.postgresql.auth.existingSecret }}
{{- else }}
{{- include "autosre.secretName" . }}
{{- end }}
{{- else }}
{{- if .Values.externalDatabase.existingSecret }}
{{- .Values.externalDatabase.existingSecret }}
{{- else }}
{{- include "autosre.secretName" . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Return Redis host
*/}}
{{- define "autosre.redis.host" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" (include "autosre.fullname" .) }}
{{- else }}
{{- .Values.externalRedis.host }}
{{- end }}
{{- end }}

{{/*
Return Redis port
*/}}
{{- define "autosre.redis.port" -}}
{{- if .Values.redis.enabled }}
{{- printf "6379" }}
{{- else }}
{{- .Values.externalRedis.port | toString }}
{{- end }}
{{- end }}

{{/*
Return Redis secret name
*/}}
{{- define "autosre.redis.secretName" -}}
{{- if .Values.redis.enabled }}
{{- if .Values.redis.auth.existingSecret }}
{{- .Values.redis.auth.existingSecret }}
{{- else }}
{{- include "autosre.secretName" . }}
{{- end }}
{{- else }}
{{- if .Values.externalRedis.existingSecret }}
{{- .Values.externalRedis.existingSecret }}
{{- else }}
{{- include "autosre.secretName" . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Return Neo4j URI
*/}}
{{- define "autosre.neo4j.uri" -}}
{{- if .Values.neo4j.enabled }}
{{- printf "bolt://%s-neo4j:7687" (include "autosre.fullname" .) }}
{{- else }}
{{- .Values.externalNeo4j.uri }}
{{- end }}
{{- end }}

{{/*
Return Neo4j username
*/}}
{{- define "autosre.neo4j.username" -}}
{{- if .Values.neo4j.enabled }}
{{- printf "neo4j" }}
{{- else }}
{{- .Values.externalNeo4j.username }}
{{- end }}
{{- end }}

{{/*
Return Neo4j secret name
*/}}
{{- define "autosre.neo4j.secretName" -}}
{{- if .Values.neo4j.enabled }}
{{- include "autosre.secretName" . }}
{{- else }}
{{- if .Values.externalNeo4j.existingSecret }}
{{- .Values.externalNeo4j.existingSecret }}
{{- else }}
{{- include "autosre.secretName" . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Return image pull secrets
*/}}
{{- define "autosre.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
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

{{/*
Checksum for config/secret changes to trigger pod restart
*/}}
{{- define "autosre.checksums" -}}
checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
checksum/secret: {{ include (print $.Template.BasePath "/secret.yaml") . | sha256sum }}
{{- end }}
