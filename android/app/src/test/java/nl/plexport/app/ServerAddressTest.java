package nl.plexport.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class ServerAddressTest {
    @Test public void normalizesExplicitNasOrigin() {
        assertEquals("http://192.168.1.100:8765/", ServerAddress.normalize(" http://192.168.1.100:8765 "));
        assertEquals("https://truenas.local/", ServerAddress.normalize("https://TrueNAS.local/"));
        assertEquals("http://[fd00::70]:8765/", ServerAddress.normalize("http://[fd00::70]:8765"));
    }
    @Test public void rejectsCredentialsAndHiddenUrlParts() {
        for (String input : new String[] {"javascript:alert(1)", "file:///etc/passwd", "content://provider/file",
                "http://admin:password@192.168.1.100", "http://192.168.1.100/#settings",
                "http://192.168.1.100/?secret=x", "http://192.168.1.100/app", "http://192.168.1.100:65536",
                "http://192.168.1.100:0", "192.168.1.100", "http://192.168.1.100\\@evil.test"}) {
            try { ServerAddress.normalize(input); fail(input); } catch (IllegalArgumentException expected) {}
        }
    }
    @Test public void restrictsNavigationToExactSchemeHostAndPort() {
        String server = "http://192.168.1.100:8765/";
        assertTrue(ServerAddress.sameOrigin(server, server + "#settings"));
        assertTrue(ServerAddress.sameOrigin(server, server + "api/jobs"));
        for (String candidate : new String[] {"https://192.168.1.100:8765/", "http://192.168.1.100/",
                "http://192.168.1.100.evil.test:8765/", "http://evil.test/", "file:///sdcard/x",
                "content://provider/x", "intent://anything", "javascript:alert(1)",
                "http://user@192.168.1.100:8765/"}) {
            assertFalse(candidate, ServerAddress.sameOrigin(server, candidate));
        }
        assertTrue(ServerAddress.sameOrigin("https://nas.local/", "https://NAS.local:443/api/status"));
    }
}
