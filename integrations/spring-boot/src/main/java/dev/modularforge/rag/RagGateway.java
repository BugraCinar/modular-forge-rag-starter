package dev.modularforge.rag;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

public final class RagGateway {
    private static final Set<Integer> CLIENT_ERRORS = Set.of(400, 403, 404, 409, 410, 413, 415, 422, 429);
    private static final String ERROR = "{\"error\":{\"code\":\"rag_request_failed\",\"message\":\"RAG request could not be completed.\"}}";
    private final RagProperties properties;
    private final RestClient client;

    public RagGateway(RagProperties properties, RestClient client) {
        this.properties = properties;
        this.client = client;
    }

    String token(RagIdentity identity, String scope) {
        Instant now = Instant.now();
        return Jwts.builder().header().type("rag-delegation+jwt").and()
                .issuer(properties.issuer()).subject(identity.subject()).audience().add(properties.audience()).and()
                .issuedAt(Date.from(now)).notBefore(Date.from(now)).expiration(Date.from(now.plusSeconds(60)))
                .id(UUID.randomUUID().toString()).claim("type", "rag-delegation")
                .claim("tenant", identity.tenant()).claim("groups", identity.groups()).claim("scope", List.of(scope))
                .signWith(Keys.hmacShaKeyFor(Base64.getDecoder().decode(properties.delegationKey())), Jwts.SIG.HS256)
                .compact();
    }

    public ResponseEntity<String> forward(HttpMethod method, String path, RagIdentity identity, String scope, String body, String key) {
        if (body != null && body.getBytes(StandardCharsets.UTF_8).length > 2_100_000) {
            return ResponseEntity.status(413).contentType(MediaType.APPLICATION_JSON).body(ERROR);
        }
        if (key != null && !key.matches("[a-zA-Z0-9_.:-]{1,128}")) {
            return ResponseEntity.status(422).contentType(MediaType.APPLICATION_JSON).body(ERROR);
        }
        try {
            var request = client.method(method).uri(path)
                    .header("Authorization", "Bearer " + token(identity, scope))
                    .contentType(MediaType.APPLICATION_JSON);
            if (key != null) request.header("Idempotency-Key", key);
            if (body != null) request.body(body);
            return request.exchange((sent, result) -> {
                int status = result.getStatusCode().value();
                if (status == 204) return ResponseEntity.noContent().build();
                if (status < 200 || status >= 300) {
                    return ResponseEntity.status(CLIENT_ERRORS.contains(status) ? status : 503)
                            .contentType(MediaType.APPLICATION_JSON).body(ERROR);
                }
                byte[] content = result.getBody().readNBytes(1_000_001);
                if (content.length > 1_000_000) {
                    return ResponseEntity.status(503).contentType(MediaType.APPLICATION_JSON).body(ERROR);
                }
                return ResponseEntity.status(status).contentType(MediaType.APPLICATION_JSON)
                        .body(new String(content, StandardCharsets.UTF_8));
            });
        } catch (RestClientException exception) {
            return ResponseEntity.status(503).contentType(MediaType.APPLICATION_JSON).body(ERROR);
        }
    }
}
