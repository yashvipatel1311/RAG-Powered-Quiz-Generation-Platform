import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Login
        login_res = await client.post("http://localhost:8000/api/auth/login", json={
            "email": "admin@academix.ai",
            "password": "password123"
        })
        print("Login status:", login_res.status_code)
        if login_res.status_code != 200:
            print("Login error:", login_res.text)
            return
        
        token = login_res.json()["access_token"]
        print("Got token.")
        
        # 2. Get notices
        notices_res = await client.get("http://localhost:8000/api/notices/", headers={
            "Authorization": f"Bearer {token}"
        })
        print("Notices status:", notices_res.status_code)
        print("Notices body:", notices_res.text)

if __name__ == "__main__":
    asyncio.run(main())
