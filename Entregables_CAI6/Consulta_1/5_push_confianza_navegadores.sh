#!/usr/bin/env bash
# PoC de modelo push para distribuir el certificado CA raiz a navegadores/sistema.

set -euo pipefail

CA_CERT_PATH="${1:-}"
CA_NICKNAME="${2:-INSEGUS-CA-ROOT}"

if [[ -z "$CA_CERT_PATH" || ! -f "$CA_CERT_PATH" ]]; then
    echo "Uso: $0 <ruta_ca_root.pem|crt> [NOMBRE_CA]" >&2
    exit 1
fi

install_macos() {
    echo "[INFO] Instalando CA en llavero del sistema (macOS)..."
    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$CA_CERT_PATH"
}

install_debian_like() {
    echo "[INFO] Instalando CA en trust store del sistema (Debian/Ubuntu)..."
    sudo cp "$CA_CERT_PATH" "/usr/local/share/ca-certificates/${CA_NICKNAME}.crt"
    sudo update-ca-certificates
}

install_rhel_like() {
    echo "[INFO] Instalando CA en trust store del sistema (RHEL/CentOS/Fedora)..."
    sudo cp "$CA_CERT_PATH" "/etc/pki/ca-trust/source/anchors/${CA_NICKNAME}.crt"
    sudo update-ca-trust
}

install_firefox_profiles() {
    if ! command -v certutil >/dev/null 2>&1; then
        echo "[WARN] certutil no disponible; se omite push en perfiles Firefox"
        return
    fi

    local profiles_dir="$HOME/.mozilla/firefox"
    if [[ ! -d "$profiles_dir" ]]; then
        echo "[INFO] No se encontraron perfiles de Firefox"
        return
    fi

    shopt -s nullglob
    for profile in "$profiles_dir"/*.default*; do
        if [[ -d "$profile" ]]; then
            echo "[INFO] Añadiendo CA a perfil Firefox: $profile"
            certutil -A -n "$CA_NICKNAME" -t "C,," -i "$CA_CERT_PATH" -d "sql:$profile" || true
        fi
    done
}

install_windows_via_gpo() {
    cat <<'EOF'
[INFO] Para Windows en entorno corporativo, el push se hace por GPO:
   1. Copiar el .crt al recurso \\servidor\netlogon\ca\insegus_root.crt
   2. Group Policy Management -> Equipo -> Configuracion de Windows
      -> Configuracion de seguridad -> Politicas de clave publica
      -> Entidades emisoras raiz de confianza -> Importar
   3. gpupdate /force en los endpoints

   Alternativa fuera de dominio (PowerShell admin):
      Import-Certificate -FilePath C:\insegus_root.crt -CertStoreLocation Cert:\LocalMachine\Root
EOF
}

OS_KIND="$(uname -s)"
case "$OS_KIND" in
    Darwin)
        install_macos
        ;;
    Linux)
        if command -v update-ca-certificates >/dev/null 2>&1; then
            install_debian_like
        elif command -v update-ca-trust >/dev/null 2>&1; then
            install_rhel_like
        else
            echo "[WARN] No se detecta gestor de trust store Linux"
        fi
        ;;
    MINGW*|CYGWIN*|MSYS*)
        install_windows_via_gpo
        ;;
    *)
        echo "[WARN] OS no reconocido ($OS_KIND); push manual requerido"
        install_windows_via_gpo
        ;;
esac

install_firefox_profiles

echo "[OK] Push de confianza completado. Orquestar por MDM (Intune/Jamf) o GPO en produccion."