package dev.modularforge.rag;

import java.util.List;

public record RagIdentity(String subject, String tenant, List<String> groups) {
    public RagIdentity {
        groups = List.copyOf(groups);
    }
}
