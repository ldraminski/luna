# Nagłówki bezpieczeństwa dla stron i API Luny (29.09.2026). Dołączane w KAŻDEJ sekcji location, bo add_header
# w location kasuje nagłówki z poziomu server (pułapka nginx — wcześniej przez to strony nie miały żadnych).
# Widgety AI (/widgets/) mają osobną, ostrzejszą politykę w nginx.conf.
add_header X-Content-Type-Options nosniff always;
add_header Referrer-Policy no-referrer always;
add_header Strict-Transport-Security "max-age=31536000" always;
add_header Permissions-Policy "microphone=(self), camera=(self), geolocation=(), payment=(), usb=()" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; connect-src 'self'; frame-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;
