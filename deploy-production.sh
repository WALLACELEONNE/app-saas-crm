#!/bin/bash
# Configuração de Produção Agro CRM
# Frontend: crm.apoctecnologia.com.br
# Backend:  api.apoctecnologia.com.br

echo "=== Configuração de Produção ==="

# DOMÍNIOS
FRONTEND_DOMAIN="crm.apoctecnologia.com.br"
BACKEND_DOMAIN="api.apoctecnologia.com.br"
EMAIL="wallace.lc.souza@gmail.com"

# ... (resto do script)

# 2. Atualizar traefik.yml para HTTPS
cat > traefik/traefik.yml << EOF
global:
  checkNewVersion: true
  sendAnonymousUsage: false

api:
  dashboard: true
  insecure: true

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true
  
  websecure:
    address: ":443"
    http:
      tls:
        certResolver: letsencrypt

certificatesResolvers:
  letsencrypt:
    acme:
      email: $EMAIL
      storage: /acme/acme.json
      httpChallenge:
        entryPoint: web
      domains:
        - main: "$DOMAIN"

log:
  level: INFO

accessLog:
  filePath: /dev/stdout

providers:
  docker:
    network: internal
    exposedByDefault: true
  file:
    directory: /etc/traefik/dynamic.yml
    watch: true
EOF

echo "✓ traefik.yml atualizado para $DOMAIN"

# 3. Atualizar CORS no backend
sed -i "s|http://localhost|http://$DOMAIN|g" docker-compose.yml

echo "✓ CORS atualizado para $DOMAIN"

# 4. Reiniciar stack
docker-compose restart traefik

echo "=== Reiniciando Traefik ==="
sleep 5

# 5. Testar
echo ""
echo "=== Testando configuração ==="
curl -sI https://$DOMAIN/api/health || echo "Aguardando certificado SSL..."
curl -s http://$DOMAIN/api/health || echo "HTTP disponível após HTTPS"

echo ""
echo "=== URLs de Acesso ==="
echo "HTTP:  http://$DOMAIN"
echo "HTTPS: https://$DOMAIN (em breve com SSL)"
echo "Dash:  http://localhost:8080/dashboard/"