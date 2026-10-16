package dev.modularforge.rag;

import java.util.UUID;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/rag")
@ConditionalOnProperty(name = "app.modules.rag.enabled", havingValue = "true")
public class RagController {
    private final RagGateway gateway;
    private final RagIdentityResolver identities;

    public RagController(RagGateway gateway, RagIdentityResolver identities) {
        this.gateway = gateway;
        this.identities = identities;
    }

    @PostMapping("/query")
    ResponseEntity<String> query(@RequestBody String body, Authentication account) {
        return gateway.forward(HttpMethod.POST, "/v1/query", identities.resolve(account), "rag:read", body, null);
    }

    @PostMapping("/search")
    ResponseEntity<String> search(@RequestBody String body, Authentication account) {
        return gateway.forward(HttpMethod.POST, "/v1/search", identities.resolve(account), "rag:read", body, null);
    }

    @PostMapping("/documents")
    ResponseEntity<String> enqueue(@RequestBody String body, @RequestHeader("Idempotency-Key") String key, Authentication account) {
        return gateway.forward(HttpMethod.POST, "/v1/documents", identities.resolve(account), "rag:write", body, key);
    }

    @GetMapping("/documents/{id}")
    ResponseEntity<String> document(@PathVariable UUID id, Authentication account) {
        return gateway.forward(HttpMethod.GET, "/v1/documents/" + id, identities.resolve(account), "rag:read", null, null);
    }

    @DeleteMapping("/documents/{id}")
    ResponseEntity<String> delete(@PathVariable UUID id, Authentication account) {
        return gateway.forward(HttpMethod.DELETE, "/v1/documents/" + id, identities.resolve(account), "rag:write", null, null);
    }

    @GetMapping("/jobs/{id}")
    ResponseEntity<String> job(@PathVariable UUID id, Authentication account) {
        return gateway.forward(HttpMethod.GET, "/v1/jobs/" + id, identities.resolve(account), "rag:write", null, null);
    }
}
