import cloudscraper
import os

API_URL = "https://xyy.huijiwiki.com/api.php"
FILENAMES_PATH = "filenames.txt"


def load_filenames(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到")
        return []
    except Exception as e:
        print(f"读取文件 {file_path} 时出错: {e}")
        return []


scraper = cloudscraper.create_scraper()


def download_file(file_name):
    try:
        params = {
            "action": "query",
            "prop": "imageinfo",
            "titles": f"File:{file_name}",
            "iiprop": "url",
            "format": "json"
        }

        response = scraper.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if "imageinfo" in page_data:
                file_url = page_data["imageinfo"][0]["url"]
                print(f"正在下载: {file_name} -> {file_url}")

                file_response = scraper.get(file_url, stream=True)
                file_response.raise_for_status()

                safe_name = os.path.basename(file_name)
                with open(safe_name, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"{file_name} 下载完成")
                return

        print(f"未找到文件 {file_name}")
    except Exception as e:
        print(f"下载 {file_name} 时出错: {e}")


def main():
    filenames = load_filenames(FILENAMES_PATH)
    if not filenames:
        print("文件名列表为空或加载失败")
        return

    for file in filenames:
        download_file(file)


if __name__ == "__main__":
    main()
