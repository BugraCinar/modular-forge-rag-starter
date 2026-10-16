package dev.modularforge.rag;

import java.net.http.HttpClient;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "app.modules.rag.enabled", havingValue = "true")
@EnableConfigurationProperties(RagProperties.class)
public class RagConfiguration {
    @Bean
    @ConditionalOnMissingBean(RagIdentityResolver.class)
    RagIdentityResolver ragIdentityResolver(RagProperties properties) {
        return new PrivateRagIdentityResolver(properties.issuer());
    }

    @Bean
    RagGateway ragGateway(RagProperties properties) {
        var http = HttpClient.newBuilder().connectTimeout(properties.timeout())
                .followRedirects(HttpClient.Redirect.NEVER).build();
        var factory = new JdkClientHttpRequestFactory(http);
        factory.setReadTimeout(properties.timeout());
        return new RagGateway(properties, RestClient.builder().baseUrl(properties.url()).requestFactory(factory).build());
    }
}
