# Cloudflare Zero Trust Tunnel - Agro CRM
# ============================================

# Passo 1: Obtenha o token em:
# https://one.dash.cloudflare.com → Zero Trust → Networks → Tunnels
# Clique em "Add a tunnel" → Configure comdocker → Copie o token

# Passo 2: Crie o arquivo .env
# ============================================
cat > .env << 'EOF'
# Cloudflare Tunnel Token (obtenha no Dashboard)
TUNNEL_TOKEN=SEU_TOKEN_AQUI
EOF

# Passo 3: Atualize o docker-compose.yml
# ============================================
# Remova a exposição direta das portas 80/443 do Traefik
# O tunnel cuidará do roteamento