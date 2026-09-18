# ============================================================
# Despliegue en Azure App Service (Linux · Python · sin contenedor)
# ============================================================
# Requisitos previos:
#   1. Tener instalada la Azure CLI  →  https://learn.microsoft.com/cli/azure/install-azure-cli
#   2. Haber iniciado sesión:  az login
#   3. (Opcional) Tener una suscripción activa con créditos (la de estudiante vale).
#
# NOTA: Los archivos grandes del grafo DIMAC (USA-road-d.USA.co / .gr)
#       pesan ~2-3 GB. Azure App Service acepta ZIP de hasta 2 GB en el plan gratuito.
#       Si los archivos de DIMAC superan ese límite, se pueden subir a Azure Blob Storage
#       y descargarlos en el startup. Para la hackathon, se pueden incluir directamente.
# ============================================================

# ---------- Variables — EDITA ESTAS 3 ----------
$RESOURCE_GROUP = "hackathon-urjc-rg"
$APP_NAME       = "hackathon-urjc-api"      # Será https://<APP_NAME>.azurewebsites.net
$LOCATION        = "westeurope"               # Centro de datos más cercano a España
# ------------------------------------------------

# 1. Crear grupo de recursos (si no existe)
az group create --name $RESOURCE_GROUP --location $LOCATION

# 2. Crear App Service Plan (Linux, SKU B1 = básico, suficiente para la hackathon)
#    Para la hackathon se puede usar F1 (gratis) pero solo 1 GB RAM → puede fallar con scipy/ortools.
#    B1 tiene 1.75 GB RAM y es el mínimo recomendado.
az appservice plan create `
    --name "${APP_NAME}-plan" `
    --resource-group $RESOURCE_GROUP `
    --is-linux `
    --sku B1

# 3. Crear la Web App con runtime Python 3.12
az webapp create `
    --resource-group $RESOURCE_GROUP `
    --plan "${APP_NAME}-plan" `
    --name $APP_NAME `
    --runtime "PYTHON:3.12"

# 4. Configurar variables de entorno en Azure
az webapp config appsettings set `
    --resource-group $RESOURCE_GROUP `
    --name $APP_NAME `
    --settings `
        ENV=production `
        ALLOWED_ORIGINS="*" `
        SCM_DO_BUILD_DURING_DEPLOYMENT=true

# 5. Configurar el comando de inicio (startup.sh)
az webapp config set `
    --resource-group $RESOURCE_GROUP `
    --name $APP_NAME `
    --startup-file "startup.sh"

# 6. Desplegar el código (ZIP deploy desde el directorio actual)
#    az webapp up hace todo: empaqueta, sube y construye.
az webapp up `
    --resource-group $RESOURCE_GROUP `
    --name $APP_NAME `
    --runtime "PYTHON:3.12"

# ============================================================
# ¡Listo! La API estará en:
#   https://<APP_NAME>.azurewebsites.net/health
#   https://<APP_NAME>.azurewebsites.net/docs   (solo si ENV != production)
#
# Comandos útiles:
#   Ver logs en tiempo real:
#     az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME
#
#   Reiniciar la app:
#     az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME
#
#   Cambiar ALLOWED_ORIGINS al dominio del frontend:
#     az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $APP_NAME --settings ALLOWED_ORIGINS="https://tufrontend.com"
# ============================================================
