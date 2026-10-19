import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// 自托管 / 局域网刷机：手填 URL 往往指向本机（http://192.168.x.x:3000/firmware/xxx.bin）。
// 这类地址同样允许经此代理下载，浏览器端只访问同源地址，避免 CORS 问题。
const PRIVATE_HOST_RE =
  /^(localhost|127\.0\.0\.1|::1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})$/;

export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get("url");
  if (!url) {
    return NextResponse.json({ error: "Missing url param" }, { status: 400 });
  }

  try {
    const parsed = new URL(url);
    const isGithub =
      parsed.hostname === "github.com" ||
      parsed.hostname.endsWith(".githubusercontent.com");
    // 局域网/本机固件（例如 webapp/public/firmware/*.bin）
    const isLocalBin =
      PRIVATE_HOST_RE.test(parsed.hostname) &&
      parsed.pathname.toLowerCase().endsWith(".bin");
    if (!isGithub && !isLocalBin) {
      return NextResponse.json(
        { error: "Only GitHub URLs or LAN .bin URLs are allowed" },
        { status: 403 },
      );
    }
  } catch {
    return NextResponse.json({ error: "Invalid URL" }, { status: 400 });
  }

  try {
    const upstream = await fetch(url, { redirect: "follow", cache: "no-store" });
    if (!upstream.ok) {
      return new NextResponse(`Upstream returned ${upstream.status}`, {
        status: upstream.status,
      });
    }

    const body = upstream.body;
    if (!body) {
      return NextResponse.json({ error: "Empty response" }, { status: 502 });
    }

    const contentLength = upstream.headers.get("content-length");
    const headers: Record<string, string> = {
      "content-type": "application/octet-stream",
      "cache-control": "no-store",
    };
    if (contentLength) {
      headers["content-length"] = contentLength;
    }

    return new NextResponse(body, { status: 200, headers });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Download failed";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
