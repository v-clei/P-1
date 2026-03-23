import csv
import json
import unicodedata
from difflib import get_close_matches
import requests


INPUT_CSV = "input.csv"
OUTPUT_CSV = "resultado.csv"
IBGE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
CORRECAO_URL = "https://mynxlubykylncinttggu.functions.supabase.co/ibge-submit"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6ImR0TG03UVh1SkZPVDJwZEciLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL215bnhsdWJ5a3lsbmNpbnR0Z2d1LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI5ZjQwYmFiMC1kMDc0LTQ4YmEtYjZkNC03NjEzZThjZDY5ZDIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzc0MzAyMTkyLCJpYXQiOjE3NzQyOTg1OTIsImVtYWlsIjoidml0b3JhbGJhMjAwMkBnbWFpbC5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoidml0b3JhbGJhMjAwMkBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwibm9tZSI6IlZpdG9yIEJhem90dGkgQWxiYSIsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwic3ViIjoiOWY0MGJhYjAtZDA3NC00OGJhLWI2ZDQtNzYxM2U4Y2Q2OWQyIn0sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3NzQyOTg1OTJ9XSwic2Vzc2lvbl9pZCI6IjA4MzkzNjk5LWExOGYtNDVjYy04MTkxLTQ2NTlkY2I2MTllYyIsImlzX2Fub255bW91cyI6ZmFsc2V9.2TLaioa5HWCp_WjbNQZEcIPOZcQVy_aqgoH6lh590d4"


def formatar_nome(texto):
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def ler_input_csv(caminho_arquivo):
    linhas = []
    with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
        reader = csv.DictReader(arquivo)
        for row in reader:
            linhas.append(
                {
                    "municipio_input": row["municipio"].strip(),
                    "municipio_formatado": formatar_nome(row["municipio"]),
                    "populacao_input": int(row["populacao"]),
                }
            )
    return linhas


def buscar_e_indexar_ibge():
    resposta = requests.get(IBGE_URL, timeout=30)
    resposta.raise_for_status()
    municipios_ibge = resposta.json()
    indice = {}
    for item in municipios_ibge:
        indice[formatar_nome(item["nome"])] = item
    return indice


def montar_linha_ok(nome_original, populacao, item_ibge):
    return {
        "municipio_input": nome_original,
        "populacao_input": populacao,
        "municipio_ibge": item_ibge["nome"],
        "uf": item_ibge["microrregiao"]["mesorregiao"]["UF"]["sigla"],
        "regiao": item_ibge["microrregiao"]["mesorregiao"]["UF"]["regiao"]["nome"],
        "id_ibge": item_ibge["id"],
        "status": "OK",
    }


def montar_linha_falha(nome_original, populacao, status):
    return {
        "municipio_input": nome_original,
        "populacao_input": populacao,
        "municipio_ibge": "",
        "uf": "",
        "regiao": "",
        "id_ibge": "",
        "status": status,
    }


def comparar_municipios(input_rows, indice_ibge, cutoff=0.88):
    resultado = []
    chaves_ibge = list(indice_ibge.keys())

    for row in input_rows:
        nome_original = row["municipio_input"]
        nome_formatado = row["municipio_formatado"]
        populacao = row["populacao_input"]

        item_ibge = indice_ibge.get(nome_formatado)
        if item_ibge:
            resultado.append(montar_linha_ok(nome_original, populacao, item_ibge))
            continue

        matches = get_close_matches(nome_formatado, chaves_ibge, n=1, cutoff=cutoff)
        if matches:
            item_ibge = indice_ibge[matches[0]]
            resultado.append(montar_linha_ok(nome_original, populacao, item_ibge))
        else:
            resultado.append(montar_linha_falha(nome_original, populacao, "NAO_ENCONTRADO"))

    return resultado


def calcular_estatisticas(linhas):
    total_ok = sum(1 for row in linhas if row["status"] == "OK")
    total_nao_encontrado = sum(1 for row in linhas if row["status"] == "NAO_ENCONTRADO")
    total_erro_api = sum(1 for row in linhas if row["status"] == "ERRO_API")

    ok_unicos = {}
    for row in linhas:
        if row["status"] == "OK" and row["id_ibge"] not in ok_unicos:
            ok_unicos[row["id_ibge"]] = row

    total_municipios = len(ok_unicos) + total_nao_encontrado + total_erro_api
    pop_total_ok = sum(row["populacao_input"] for row in ok_unicos.values())

    soma_por_regiao = {}
    quantidade_por_regiao = {}
    for row in ok_unicos.values():
        regiao = row["regiao"]
        soma_por_regiao[regiao] = soma_por_regiao.get(regiao, 0) + row["populacao_input"]
        quantidade_por_regiao[regiao] = quantidade_por_regiao.get(regiao, 0) + 1

    medias_por_regiao = {
        regiao: soma_por_regiao[regiao] / quantidade_por_regiao[regiao]
        for regiao in soma_por_regiao
    }

    return {
        "total_municipios": total_municipios,
        "total_ok": total_ok,
        "total_nao_encontrado": total_nao_encontrado,
        "total_erro_api": total_erro_api,
        "pop_total_ok": pop_total_ok,
        "medias_por_regiao": medias_por_regiao,
    }


def salvar_resultado_csv(linhas, caminho_saida):
    colunas = [
        "municipio_input",
        "populacao_input",
        "municipio_ibge",
        "uf",
        "regiao",
        "id_ibge",
        "status",
    ]
    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=colunas)
        writer.writeheader()
        writer.writerows(linhas)


def enviar_resposta_final(estatisticas):
    payload = {"stats": estatisticas}
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    resposta = requests.post(CORRECAO_URL, headers=headers, json=payload, timeout=30)
    resposta.raise_for_status()
    return resposta.json()


def main():
    input_rows = ler_input_csv(INPUT_CSV)

    try:
        indice_ibge = buscar_e_indexar_ibge()
        linhas_processadas = comparar_municipios(input_rows, indice_ibge)
    except requests.RequestException as e:
        print(f"Erro ao chamar a API do IBGE: {e}")
        linhas_processadas = [
            montar_linha_falha(row["municipio_input"], row["populacao_input"], "ERRO_API")
            for row in input_rows
        ]

    salvar_resultado_csv(linhas_processadas, OUTPUT_CSV)
    estatisticas = calcular_estatisticas(linhas_processadas)

    print(json.dumps(estatisticas, indent=2, ensure_ascii=False))
    print(f"Arquivo gerado: {OUTPUT_CSV}")

    try:
        resposta_final = enviar_resposta_final(estatisticas)
        print(json.dumps(resposta_final, indent=2, ensure_ascii=False))
        print("Score:", resposta_final.get("score"))
    except requests.RequestException as e:
        print(f"Erro ao enviar resposta final: {e}")


if __name__ == "__main__":
    main()