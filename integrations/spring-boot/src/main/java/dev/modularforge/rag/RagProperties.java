package dev.modularforge.rag;

import java.net.URI;
import java.time.Duration;
import java.util.Base64;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("app.rag")
public record RagProperties(String url, String issuer, String audience, String delegationKey, Duration timeout) {
    public RagProperties {
        url = url == null ? "http://127.0.0.1:8090" : url;
        issuer = issuer == null ? "forge-spring" : issuer;
        audience = audience == null ? "modular-forge-rag" : audience;
        timeout = timeout == null ? Duration.ofSeconds(90) : timeout;
        URI parsed = URI.create(url);
        if (!("https".equals(parsed.getScheme()) || "http".equals(parsed.getScheme()))
                || parsed.getHost() == null || parsed.getUserInfo() != null
                || parsed.getQuery() != null || parsed.getFragment() != null
                || !(parsed.getPath().isEmpty() || parsed.getPath().equals("/"))) {
            throw new IllegalArgumentException("RAG URL must be a fixed service origin");
        }
        if (timeout.isNegative() || timeout.isZero() || timeout.compareTo(Duration.ofMinutes(5)) > 0) {
            throw new IllegalArgumentException("RAG timeout must be 0-300 seconds");
        }
        byte[] decoded = Base64.getDecoder().decode(delegationKey == null ? "" : delegationKey);
        if (decoded.length != 32 || java.util.stream.IntStream.range(0, decoded.length).map(i -> decoded[i]).distinct().count() < 16) {
            throw new IllegalArgumentException("RAG key must contain 32 random Base64 bytes");
        }
    }

    @Override
    public String toString() {
        return "RagProperties[issuer=" + issuer + ", credentials=redacted]";
    }
}
