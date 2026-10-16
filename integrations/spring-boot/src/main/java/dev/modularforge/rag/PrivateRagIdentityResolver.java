package dev.modularforge.rag;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.server.ResponseStatusException;

public final class PrivateRagIdentityResolver implements RagIdentityResolver {
    private final String issuer;

    public PrivateRagIdentityResolver(String issuer) {
        this.issuer = issuer;
    }

    @Override
    public RagIdentity resolve(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()
                || !(authentication.getDetails() instanceof Long id) || id <= 0) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Current account is required");
        }
        boolean admin = authentication.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
        boolean user = authentication.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_USER"));
        if (admin == user) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Account role is ambiguous");
        }
        String subject = (admin ? "admin:" : "user:") + id;
        return new RagIdentity(subject, "personal:" + issuer + ":" + subject, List.of());
    }
}
