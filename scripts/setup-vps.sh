#!/bin/bash
set -e
echo "============================================"
echo " Setup VPS - portal-noticias (espelha profissional-os)"
echo " Web Next.js (TS) + API Django + Firebase + Redis"
echo " 3 envs: dev(3101/5101) homolog(3102/5102) prod(3103/5103)"
echo "============================================"
export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash; export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; fi
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm install 20; nvm use 20; nvm alias default 20
npm install -g pm2
sudo apt update && sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx redis-server
for ENV in dev homolog prod; do
  DIR="/home/apps/portal-$ENV"
  if [ ! -d "$DIR/.git" ]; then echo ">>> Clone $ENV -> $DIR"; mkdir -p /home/apps; git clone -b main https://github.com/Alex-Buttielie/portal-noticias.git "$DIR" || true; fi
done
sudo tee /etc/nginx/sites-available/portal-dev <<'NGINX'
server { listen 80; server_name dev.portal-noticias.com.br;
  location /api/ { proxy_pass http://localhost:5101; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }
  location / { proxy_pass http://localhost:3101; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection 'upgrade'; proxy_set_header Host $host; }
}
NGINX
sudo tee /etc/nginx/sites-available/portal-homolog <<'NGINX'
server { listen 80; server_name homolog.portal-noticias.com.br;
  location /api/ { proxy_pass http://localhost:5102; proxy_set_header Host $host; }
  location / { proxy_pass http://localhost:3102; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection 'upgrade'; proxy_set_header Host $host; }
}
NGINX
sudo tee /etc/nginx/sites-available/portal-prod <<'NGINX'
server { listen 80; server_name portal-noticias.com.br www.portal-noticias.com.br;
  location /api/ { proxy_pass http://localhost:5103; proxy_set_header Host $host; }
  location / { proxy_pass http://localhost:3103; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection 'upgrade'; proxy_set_header Host $host; }
}
NGINX
sudo ln -sf /etc/nginx/sites-available/portal-dev /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/portal-homolog /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/portal-prod /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default; sudo nginx -t && sudo systemctl restart nginx && sudo systemctl enable nginx
echo ">>> Setup ok. Configure DNS + certbot --nginx -d dev.portal-noticias.com.br etc"
