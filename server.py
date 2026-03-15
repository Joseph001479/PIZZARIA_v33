#!/usr/bin/env python3
"""
Servidor intermediário - Pizzaria Barbosa
Ponte entre checkout.html e API SkalePay
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import base64
import os

app = Flask(__name__)
CORS(app)

# ========== CONFIGURAÇÃO - EDITE AQUI ==========
SKALE_SECRET_KEY = os.environ.get("SKALE_SECRET_KEY", "")
SKALE_API_URL    = "https://api.conta.skalepay.com.br/v1"
# ================================================

def auth_header():
    """Basic Auth: base64(chave:)"""
    token = base64.b64encode(f"{SKALE_SECRET_KEY}:".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
        "User-Agent":    "python-requests/2.31.0",
        "Accept-Encoding": "gzip, deflate",
        "Connection":    "keep-alive"
    }


@app.route("/criar-pix", methods=["POST"])
def criar_pix():
    try:
        d = request.get_json()

        # Formato EXATO que a SkalePay espera
        body = {
            "amount":        d["amount"],          # centavos ex: 6890
            "paymentMethod": "pix",
            "customer": {
                "name":      d["customer"]["name"],
                "email":     d["customer"]["email"],
                "phone":     d["customer"]["phone"],
                "document": {
                    "number": d["customer"]["document"],  # somente números
                    "type":   "cpf"
                },
                "address": {
                    "street":       d["customer"]["street"],
                    "streetNumber": d["customer"]["streetNumber"],
                    "complement":   d["customer"].get("complement", ""),
                    "neighborhood": d["customer"]["neighborhood"],
                    "city":         d["customer"]["city"],
                    "state":        d["customer"]["state"],
                    "zipCode":      d["customer"]["zipCode"],  # somente números
                    "country":      "BR"
                }
            },
            "items": [
                {
                    "title":     d["item"]["title"],
                    "quantity":  1,
                    "unitPrice": d["amount"],
                    "tangible":  True
                }
            ],
            "pix": {
                "expiresInDays": 1   # campo correto conforme documentação
            }
        }

        print(f"\n>>> Enviando para SkalePay:")
        print(f"    Amount: {body['amount']}")
        print(f"    Customer: {body['customer']['name']} / {body['customer']['email']}")
        print(f"    Document: {body['customer']['document']['number']}")

        resp = requests.post(
            f"{SKALE_API_URL}/transactions",
            json=body,
            headers=auth_header(),
            timeout=30
        )

        print(f"\n<<< Resposta SkalePay ({resp.status_code}):")
        print(f"    Headers: {dict(resp.headers)}")
        print(f"    Body raw: {repr(resp.text[:500])}")

        # Tratar resposta vazia
        if not resp.text or not resp.text.strip():
            return jsonify({
                "erro":     True,
                "mensagem": f"SkalePay retornou resposta vazia (status {resp.status_code})"
            }), 500

        try:
            resultado = resp.json()
        except Exception as e:
            return jsonify({
                "erro":     True,
                "mensagem": f"Resposta inválida da SkalePay: {resp.text[:200]}"
            }), 500

        print(f"    JSON: {resultado}")

        if resp.status_code not in (200, 201):
            return jsonify({
                "erro":      True,
                "mensagem":  resultado.get("message", "Erro ao criar transação"),
                "detalhes":  resultado
            }), resp.status_code

        # Extrair dados do PIX
        pix = resultado.get("pix") or {}

        # SkalePay pode retornar o QR em campos diferentes
        copia_cola   = (
            pix.get("qrCode")      or
            pix.get("copyPaste")   or
            pix.get("qrcode")      or
            pix.get("code")        or
            ""
        )
        qr_image = (
            pix.get("qrCodeImage") or
            pix.get("qrCodeUrl")   or
            pix.get("imageUrl")    or
            ""
        )

        print(f"\n    PIX copiaCola: {copia_cola[:40] if copia_cola else 'VAZIO'}...")
        print(f"    PIX qrImage:   {qr_image[:40] if qr_image else 'VAZIO'}...")

        return jsonify({
            "erro":        False,
            "id":          resultado.get("id", ""),
            "status":      resultado.get("status", ""),
            "secureUrl":   resultado.get("secureUrl", ""),
            "copiaCola":   copia_cola,
            "qrCodeImage": qr_image,
            "valor":       resultado.get("amount", 0),
            "raw":         resultado
        })

    except requests.exceptions.Timeout:
        return jsonify({"erro": True, "mensagem": "Timeout ao conectar com SkalePay"}), 504
    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"erro": True, "mensagem": str(e)}), 500


@app.route("/verificar-pix/<int:tid>", methods=["GET"])
def verificar_pix(tid):
    try:
        resp    = requests.get(f"{SKALE_API_URL}/transactions/{tid}", headers=auth_header(), timeout=15)
        dados   = resp.json()
        return jsonify({
            "id":     dados.get("id", ""),
            "status": dados.get("status", ""),
            "paidAt": dados.get("paidAt", "")
        })
    except Exception as e:
        return jsonify({"erro": True, "mensagem": str(e)}), 500


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "servidor": "Pizzaria Barbosa rodando!"})


@app.route("/testar-api", methods=["GET"])
def testar_api():
    """Testa conexão com SkalePay"""
    try:
        resp = requests.get(
            f"{SKALE_API_URL}/transactions",
            headers=auth_header(),
            timeout=15
        )
        return jsonify({
            "status_code": resp.status_code,
            "headers":     dict(resp.headers),
            "body":        resp.text[:500]
        })
    except Exception as e:
        return jsonify({"erro": str(e)})


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  🍕 Servidor Pizzaria Barbosa")
    print("  Rodando em: http://localhost:5000")
    print("="*50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
