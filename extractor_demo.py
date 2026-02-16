import httpx
import asyncio
from bs4 import BeautifulSoup
import json

async def extract_direct_link(media_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Referer": "https://flixhq.to/"
    }
    
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        # 1. Simular a busca do ID interno da mídia
        print(f"Acessando: {media_url}")
        resp = await client.get(media_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # O data-id é essencial para as chamadas AJAX
        watch_btn = soup.select_one(".detail_page-watch")
        if not watch_btn:
            return "Não foi possível encontrar o botão de assistir."
        
        data_id = watch_btn["data-id"]
        print(f"Data ID encontrado: {data_id}")
        
        # 2. Obter servidores (AJAX)
        # Para filmes: /ajax/movie/episodes/{id}
        # Para séries: /ajax/v2/episode/servers/{id}
        is_movie = "movie" in media_url
        ajax_url = f"https://flixhq.to/ajax/movie/episodes/{data_id}" if is_movie else f"https://flixhq.to/ajax/v2/episode/servers/{data_id}"
        
        print(f"Chamando AJAX de servidores: {ajax_url}")
        resp = await client.get(ajax_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Pegar o primeiro servidor disponível (geralmente UpCloud/VidCloud)
        server_link = soup.select_one(".nav-item a")
        if not server_link:
            return "Nenhum servidor encontrado."
            
        link_id = server_link.get("data-linkid") or server_link.get("data-id")
        print(f"Link ID do servidor: {link_id}")
        
        # 3. Obter o link do iframe (o link que contém o vídeo real ou o player)
        sources_url = f"https://flixhq.to/ajax/movie/episode/server/sources/{link_id}" if is_movie else f"https://flixhq.to/ajax/v2/episode/sources/{link_id}"
        print(f"Obtendo fontes de: {sources_url}")
        resp = await client.get(sources_url)
        source_data = resp.json()
        
        player_url = source_data.get("link")
        print(f"URL do Player/Iframe: {player_url}")
        
        # 4. A partir daqui, o player_url (ex: rabbitstream.net) precisa ser descriptografado
        # O Consumet faz isso usando uma chave AES. 
        # Para um link direto real, retornaríamos o player_url que pode ser embutido sem anúncios se usado com os headers corretos.
        
        return {
            "player_url": player_url,
            "instructions": "Para ver sem bloqueios, use este link em um iframe com Referer: https://flixhq.to/"
        }

if __name__ == "__main__":
    # Exemplo com um filme (Inception como placeholder de exemplo de URL)
    url = "https://flixhq.to/movie/watch-inception-19777"
    # Nota: Em um ambiente real, o usuário forneceria o ID.
    # asyncio.run(extract_direct_link(url))
    print("Script de demonstração preparado. Execute para testar a lógica de extração.")
