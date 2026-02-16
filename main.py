from fastapi import FastAPI, HTTPException, Query
import httpx
from bs4 import BeautifulSoup
import re
import json
from typing import List, Optional

app = FastAPI(title="Manus Custom Scraper API")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

class ScraperBase:
    def __init__(self):
        self.headers = {"User-Agent": USER_AGENT}

    async def get_soup(self, url: str):
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")

class FlixHQScraper(ScraperBase):
    BASE_URL = "https://flixhq.to"

    async def search(self, query: str):
        sanitized = query.replace(" ", "-")
        url = f"{self.BASE_URL}/search/{sanitized}"
        soup = await self.get_soup(url)
        results = []
        for item in soup.select(".film_list-wrap .flw-item"):
            title = item.select_one(".film-name a")["title"]
            href = item.select_one(".film-name a")["href"]
            img_el = item.select_one(".film-poster img")
            img = img_el["data-src"] if img_el.has_attr("data-src") else img_el["src"]
            results.append({
                "id": href.strip("/"),
                "title": title,
                "image": img,
                "type": "tv" if "/tv/" in href else "movie"
            })
        return results

    async def get_info(self, media_id: str):
        url = f"{self.BASE_URL}/{media_id}"
        soup = await self.get_soup(url)
        watch_btn = soup.select_one(".detail_page-watch")
        if not watch_btn:
            raise Exception("Watch button not found")
        
        data_id = watch_btn["data-id"]
        title = soup.select_one(".heading-name a").text.strip()
        
        episodes = []
        is_tv = "tv" in media_id
        
        if is_tv:
            # Em uma implementação real do Consumet, aqui buscaríamos temporadas/episódios
            # Para este MVP, retornamos o data_id como ID base
            pass
        else:
            episodes.append({"id": data_id, "title": title})
            
        return {
            "title": title,
            "data_id": data_id,
            "is_tv": is_tv,
            "episodes": episodes
        }

    async def get_sources(self, episode_id: str, is_tv: bool = False):
        # Diferentes endpoints para filmes e séries
        if is_tv:
            ajax_url = f"{self.BASE_URL}/ajax/v2/episode/servers/{episode_id}"
        else:
            ajax_url = f"{self.BASE_URL}/ajax/movie/episodes/{episode_id}"

        async with httpx.AsyncClient(headers=self.headers) as client:
            resp = await client.get(ajax_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Tentar pegar o primeiro servidor disponível
            server_el = soup.select_one(".nav-item a")
            if not server_el:
                # Se falhou no endpoint de filme, tentar o de série (fallback)
                alt_url = f"{self.BASE_URL}/ajax/v2/episode/servers/{episode_id}" if not is_tv else f"{self.BASE_URL}/ajax/movie/episodes/{episode_id}"
                resp = await client.get(alt_url)
                soup = BeautifulSoup(resp.text, "html.parser")
                server_el = soup.select_one(".nav-item a")
            
            if not server_el:
                raise Exception("Nenhum servidor encontrado para este ID")

            server_id = server_el.get("data-linkid") or server_el.get("data-id")
            
            # Segunda chamada para pegar o link do iframe/fonte
            if is_tv or "/v2/" in ajax_url:
                sources_url = f"{self.BASE_URL}/ajax/v2/episode/sources/{server_id}"
            else:
                sources_url = f"{self.BASE_URL}/ajax/movie/episode/server/sources/{server_id}"

            source_resp = await client.get(sources_url)
            return source_resp.json()

flixhq = FlixHQScraper()

@app.get("/")
async def root():
    return {"message": "Manus Custom Scraper API is running"}

@app.get("/search")
async def search(q: str = Query(..., min_length=1)):
    try:
        return await flixhq.search(q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/info/{media_id:path}")
async def info(media_id: str):
    try:
        return await flixhq.get_info(media_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/watch/{episode_id}")
async def watch(episode_id: str, is_tv: bool = False):
    try:
        return await flixhq.get_sources(episode_id, is_tv)
    except Exception as e:
        # Tentar detectar automaticamente se falhar
        try:
             return await flixhq.get_sources(episode_id, not is_tv)
        except:
             raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
