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
            img = item.select_one(".film-poster img")["data-src"]
            results.append({
                "id": href.strip("/"),
                "title": title,
                "image": img,
                "type": "tv" if "tv" in href else "movie"
            })
        return results

    async def get_info(self, media_id: str):
        url = f"{self.BASE_URL}/{media_id}"
        soup = await self.get_soup(url)
        data_id = soup.select_one(".detail_page-watch")["data-id"]
        title = soup.select_one(".heading-name a").text.strip()
        
        episodes = []
        if "tv" in media_id:
            # Lógica para pegar temporadas e episódios via AJAX
            # Por brevidade no MVP, focamos no fluxo de extração
            pass
        else:
            episodes.append({"id": data_id, "title": title})
            
        return {
            "title": title,
            "data_id": data_id,
            "episodes": episodes
        }

    async def get_sources(self, episode_id: str):
        # O Consumet usa um extrator externo (eatmynerds) para descriptografar.
        # Aqui simulamos a chamada para obter o link final.
        # Em uma implementação real, portaríamos o algoritmo de descriptografia AES.
        ajax_url = f"{self.BASE_URL}/ajax/movie/episodes/{episode_id}"
        async with httpx.AsyncClient(headers=self.headers) as client:
            resp = await client.get(ajax_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            server_id = soup.select_one(".nav-item a")["data-linkid"]
            
            # Segunda chamada para pegar o link do iframe/fonte
            source_resp = await client.get(f"{self.BASE_URL}/ajax/movie/episode/server/sources/{server_id}")
            source_data = source_resp.json()
            # source_data['link'] contém o link do RabbitStream/UpCloud
            return source_data

flixhq = FlixHQScraper()

@app.get("/")
async def root():
    return {"message": "Manus Custom Scraper API is running without blocks"}

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
async def watch(episode_id: str):
    try:
        return await flixhq.get_sources(episode_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
