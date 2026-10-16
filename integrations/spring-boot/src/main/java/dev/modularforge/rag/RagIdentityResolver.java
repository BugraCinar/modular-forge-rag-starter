package dev.modularforge.rag;

import org.springframework.security.core.Authentication;

@FunctionalInterface
public interface RagIdentityResolver {
    RagIdentity resolve(Authentication authentication);
}
