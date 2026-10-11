package nl.plexport.app;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Only an explicit HTTP(S) origin can become the trusted PlexPort server. */
public final class ServerAddress {
    private ServerAddress() {}

    public static String normalize(String value) {
        String input = value.trim();
        try {
            URI uri = new URI(input);
            String scheme = uri.getScheme();
            String host = uri.getHost();
            String path = uri.getRawPath();
            if (scheme == null || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))
                    || host == null || host.isEmpty() || uri.getRawUserInfo() != null
                    || uri.getRawQuery() != null || uri.getRawFragment() != null
                    || (path != null && !path.isEmpty() && !path.equals("/"))
                    || uri.getPort() == 0 || uri.getPort() < -1 || uri.getPort() > 65535) {
                throw new IllegalArgumentException("Gebruik alleen het NAS-adres, bijvoorbeeld http://192.168.1.100:8765");
            }
            return new URI(scheme.toLowerCase(Locale.ROOT), null, host.toLowerCase(Locale.ROOT),
                    uri.getPort(), "/", null, null).toASCIIString();
        } catch (URISyntaxException e) {
            throw new IllegalArgumentException("Dit adres is ongeldig. Gebruik http:// of https:// met je NAS-adres.");
        }
    }

    public static boolean sameOrigin(String server, String candidate) {
        try {
            URI expected = new URI(server);
            URI actual = new URI(candidate);
            return actual.getRawUserInfo() == null && actual.getHost() != null
                    && expected.getScheme().equalsIgnoreCase(actual.getScheme())
                    && expected.getHost().equalsIgnoreCase(actual.getHost())
                    && effectivePort(expected) == effectivePort(actual);
        } catch (URISyntaxException | IllegalArgumentException e) {
            return false;
        }
    }

    private static int effectivePort(URI uri) {
        if (uri.getPort() >= 0) return uri.getPort();
        return "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }
}
