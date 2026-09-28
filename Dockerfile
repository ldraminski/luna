FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.inc /etc/nginx/snippets/security-headers.inc
COPY public/ /usr/share/nginx/html/
# Numer wersji w adresach CSS/JS (i nazwa cache SW) = skrót treści — nowe wdrożenie = nowe adresy, telefon nie weźmie starego pliku z pamięci
RUN cd /usr/share/nginx/html && V=$(cat app.js api.js app.css index.html sw.js biurko.html biurko.js biurko.css regulamin.html | md5sum | cut -c1-10) \
 && sed -i "s/__V__/$V/g" index.html app.js sw.js biurko.html biurko.js regulamin.html && ! grep -l "__V__" index.html app.js sw.js biurko.html biurko.js regulamin.html
