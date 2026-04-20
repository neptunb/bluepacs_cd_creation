## Ultramar Ağı üzerinde Download Ayarı (Cloudflare için)

Merkez içi (aynı LAN)
https://cd.bluepacs.com/cd-yaz/...
Evet (Caddy + LAN)
Ev / dış dünya
https://cd.bluepacs.com/...
Hayır (LAN IP)
Ev / dış dünya
https://ultramar.bluepacs.com/cd-yaz/...
Evet (mevcut public yol)
Dışarıdan da sadece LAN hızında indirmek istiyorsan o zaman VPN (merkeze bağlanınca cd.bluepacs.com çözülür) veya başka bir tünel gerekir; saf “internetten tarayıcı, merkez dışı” senaryoda doğal olarak public URL kullanılır.

Şimdi Cloudflare için ne yapmalıyım ve nasıl?

Cloudflare tarafında yapman gerekenler iki blok: (1) DNS kaydı cd.bluepacs.com için, (2) API token (Caddy’nin Let’s Encrypt sertifikası için DNS-01).

1) DNS kaydı — cd.bluepacs.com
Cloudflare Dashboard → Websites → bluepacs.com (veya zone hangi hesaptaysa).
Sol menü DNS → Records → Add record.
Şunu gir:
Type: A
Name: cd → tam adı cd.bluepacs.com yapar (ultramar alt domain’i değil, kök bluepacs.com altında cd).
IPv4 address: Merkez sunucunun LAN IP’si (ör. 192.168.1.50). Bu makinede Docker + cd-caddy 443’ü dinliyor olmalı.
Proxy status: DNS only (gri bulut). Proxied (turuncu) açma.
TTL: Auto
Save.
Kontrol: Dışarıdan veya merkez içinden terminalde:
dig cd.bluepacs.com +short → yazdığın LAN IP görünmeli.

Not: cd kaydı bluepacs.com zone’unda olmalı. Eğer asıl zone ultramar.bluepacs.com gibi ayrı bir subdomain zone’u ise, o zone’da cd yerine tam FQDN’e göre kayıt adını ayarlarsın; senin planda genelde bluepacs.com altında cd.bluepacs.com.

2) API token — Let’s Encrypt (Caddy DNS-01)
Cloudflare → sağ üst profil ikonu → My Profile → API Tokens → Create Token.
“Edit zone DNS” şablonunu kullan (Use template).
Zone Resources:
Include → Specific zone → bluepacs.com (Caddy’nin TXT kaydı atacağı zone).
Permissions şablonda zaten yaklaşık şunlar olur:
Zone · DNS · Edit
Zone · Zone · Read
Continue to summary → Create Token → token’ı bir kere kopyala (sonra tekrar gösterilmez).
Sunucuda: Ultramar klasöründeki .env dosyasına (compose ile aynı dizinde):

CLOUDFLARE_API_TOKEN=buraya_yapistir
ACME_EMAIL=senin@email.com
Sonra:

docker compose --profile cd-lan-tls up -d --build
docker compose logs -f cd-caddy
Log’da sertifika alındığına dair mesaj görünene kadar bekle.

3) ultramar.bluepacs.com (mevcut site)
Değiştirmek zorunda değilsin — CF’de turuncu proxy ile kalsın. Ama operatör hem ultramar hem cd altında oturum taşısın diye PHP tarafında cookie:

Domain=.bluepacs.com; Secure; SameSite=None

(Önceki konuşmada geçti; bu Cloudflare panelinden değil, Ultramar/phpapi kodundan.)

4) Hızlı doğrulama listesi
Adım	Ne yapıyorsun
DNS
cd → LAN IP, DNS only
Token
Zone bluepacs.com, DNS Edit + Zone Read
Sunucu
.env → CLOUDFLARE_API_TOKEN
Compose
docker compose --profile cd-lan-tls up -d
Test
curl -sI https://cd.bluepacs.com → Server: Caddy, CF-Ray yok
Özet: Cloudflare’de tek A kaydı (gri bulut) + bir API token; geri kalanı sunucuda .env ve compose profili. ultramar kaydı için ekstra CF adımı şart değil (cookie PHP’de).


--------------
CF API Token testi için

curl "https://api.cloudflare.com/client/v4/user/tokens/verify" \
-H "Authorization: Bearer xxxxxxxxx"

xxxxxxxxx'i .env(Ultramar repo)'dan al.

---------------
cd.bluepacs.com için test:
```
dig cd.bluepacs.com +short
```

nbcd.bluepacs.com testi:
```
dig nbcd.bluepacs.com +short
```