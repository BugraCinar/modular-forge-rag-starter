package dev.modularforge.rag;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Base64;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

class RagIntegrationTest {
    private byte[] key() {
        byte[] bytes = new byte[32];
        for (int i = 0; i < 32; i++) bytes[i] = (byte)(i + 32);
        return bytes;
    }

    private RagProperties properties() {
        return new RagProperties("http://localhost:8090", "forge-spring", "modular-forge-rag",
                Base64.getEncoder().encodeToString(key()), Duration.ofSeconds(90));
    }

    @Test
    void delegationMatchesPythonContract() throws Exception {
        var gateway = new RagGateway(properties(), RestClient.create());
        String token = gateway.token(new RagIdentity("user:42", "personal:forge-spring:user:42", List.of()), "rag:read");
        var parsed = Jwts.parser().verifyWith(Keys.hmacShaKeyFor(key())).requireIssuer("forge-spring")
                .requireAudience("modular-forge-rag").build().parseSignedClaims(token);
        assertEquals("rag-delegation+jwt", parsed.getHeader().getType());
        assertEquals("rag-delegation", parsed.getPayload().get("type"));
        assertEquals(List.of("rag:read"), parsed.getPayload().get("scope"));
        assertEquals(60_000, parsed.getPayload().getExpiration().getTime()-parsed.getPayload().getIssuedAt().getTime());
        Files.createDirectories(Path.of("target"));
        Files.writeString(Path.of("target", "python-contract.jwt"), token);
    }

    @Test
    void gatewayPreserves202IdempotencyAndDelete() {
        var builder = RestClient.builder().baseUrl("http://localhost:8090");
        var server = MockRestServiceServer.bindTo(builder).build();
        var gateway = new RagGateway(properties(), builder.build());
        server.expect(requestTo("http://localhost:8090/v1/documents")).andExpect(method(HttpMethod.POST))
                .andExpect(header("Idempotency-Key", "doc-v1")).andExpect(header("Content-Type", "application/json"))
                .andExpect(request -> assertTrue(request.getHeaders().getFirst("Authorization").startsWith("Bearer ")))
                .andRespond(withStatus(org.springframework.http.HttpStatus.ACCEPTED).contentType(MediaType.APPLICATION_JSON).body("{\"status\":\"queued\"}"));
        var identity = new RagIdentity("user:42", "private", List.of());
        assertEquals(202, gateway.forward(HttpMethod.POST, "/v1/documents", identity, "rag:write", "{}", "doc-v1").getStatusCode().value());
        server.verify();
        server.reset();
        server.expect(requestTo("http://localhost:8090/v1/documents/id")).andRespond(withNoContent());
        assertEquals(204, gateway.forward(HttpMethod.DELETE, "/v1/documents/id", identity, "rag:write", null, null).getStatusCode().value());
        server.verify();
    }

    @Test
    void upstreamFailureIsSanitized() {
        var builder = RestClient.builder().baseUrl("http://localhost:8090");
        var server = MockRestServiceServer.bindTo(builder).build();
        server.expect(anything()).andRespond(withServerError().body("sensitive upstream diagnostic"));
        var response = new RagGateway(properties(), builder.build()).forward(HttpMethod.POST, "/v1/query",
                new RagIdentity("user:42", "private", List.of()), "rag:read", "{}", null);
        assertEquals(503, response.getStatusCode().value());
        assertFalse(response.getBody().contains("sensitive"));
        server.verify();
    }

    @Test
    void resolverUsesStableIdAndSeparatesAdminNamespace() {
        var resolver = new PrivateRagIdentityResolver("forge-spring");
        var user = new UsernamePasswordAuthenticationToken("mutable-name", null, List.of(new SimpleGrantedAuthority("ROLE_USER")));
        user.setDetails(42L);
        assertEquals("user:42", resolver.resolve(user).subject());
        assertEquals("personal:forge-spring:user:42", resolver.resolve(user).tenant());
        var admin = new UsernamePasswordAuthenticationToken("same-name", null, List.of(new SimpleGrantedAuthority("ROLE_ADMIN")));
        admin.setDetails(42L);
        assertEquals("admin:42", resolver.resolve(admin).subject());
        assertThrows(ResponseStatusException.class, () -> resolver.resolve(null));
        user.setDetails("42");
        assertThrows(ResponseStatusException.class, () -> resolver.resolve(user));
    }

    @Test
    void disabledModuleHasNoBeansAndNeedsNoKey() {
        new ApplicationContextRunner().withUserConfiguration(RagConfiguration.class, RagController.class)
                .withPropertyValues("app.modules.rag.enabled=false").run(context -> {
                    assertNull(context.getStartupFailure());
                    assertEquals(0, context.getBeansOfType(RagGateway.class).size());
                    assertEquals(0, context.getBeansOfType(RagController.class).size());
                    assertEquals(0, context.getBeansOfType(RagIdentityResolver.class).size());
                });
    }

    @Test
    void enabledModuleRequiresStrongIndependentKey() {
        assertThrows(IllegalArgumentException.class, () -> new RagProperties(null, null, null, "", null));
        assertFalse(properties().toString().contains(properties().delegationKey()));
        new ApplicationContextRunner().withUserConfiguration(RagConfiguration.class, RagController.class)
                .withPropertyValues("app.modules.rag.enabled=true", "app.rag.delegation-key="+properties().delegationKey())
                .run(context -> {
                    assertNull(context.getStartupFailure());
                    assertEquals(1, context.getBeansOfType(RagGateway.class).size());
                    assertEquals(1, context.getBeansOfType(RagController.class).size());
                });
    }
}
