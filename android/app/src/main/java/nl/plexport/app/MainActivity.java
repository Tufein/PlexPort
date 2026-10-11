package nl.plexport.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.annotation.SuppressLint;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.HttpAuthHandler;
import android.webkit.PermissionRequest;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebViewDatabase;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayInputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String DEFAULT_SERVER = "http://truenas.local:8765/";
    private static final int PICK_TORRENT = 42;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService loginExecutor = Executors.newSingleThreadExecutor();
    private final Runnable connectionTimeout = this::showConnectionTimeout;
    private SharedPreferences preferences;
    private String server;
    private WebView webView;
    private FrameLayout content;
    private LinearLayout errorPanel;
    private TextView errorTitle;
    private TextView errorMessage;
    private ProgressBar progress;
    private AlertDialog authDialog;
    private ValueCallback<Uri[]> fileCallback;
    private boolean pageFailed;
    private boolean finishing;
    private String sessionUser;
    private String sessionPassword;
    private int loginEpoch;
    private int webAuthAttempts;

    private void showConnectionTimeout() {
        if (webView != null) webView.stopLoading();
        showError("Je NAS antwoordt niet", "Controleer of je telefoon op hetzelfde netwerk zit en of PlexPort op je NAS draait.");
    }

    @Override public void onCreate(Bundle savedState) {
        super.onCreate(savedState);
        preferences = getSharedPreferences("plexport", MODE_PRIVATE);
        try {
            server = ServerAddress.normalize(preferences.getString("server", DEFAULT_SERVER));
        } catch (IllegalArgumentException e) {
            server = DEFAULT_SERVER;
        }
        buildLayout();
        createWebView();
        if (Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(0, this::handleBack);
        }
        if (preferences.contains("server")) loadServer();
        else showAddressDialog(true);
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private int color(int resource) { return getResources().getColor(resource, getTheme()); }

    private GradientDrawable rounded(int fill, int border, int radius) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(fill);
        shape.setCornerRadius(dp(radius));
        if (border != 0) shape.setStroke(dp(1), border);
        return shape;
    }

    private void loginLabel(LinearLayout fields, String text) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(13);
        label.setTextColor(color(R.color.text));
        label.setPadding(0, dp(18), 0, dp(8));
        fields.addView(label);
    }

    private void styleInput(EditText input) {
        input.setTextSize(16);
        input.setTextColor(color(R.color.text));
        input.setHintTextColor(color(R.color.muted));
        input.setPadding(dp(14), dp(12), dp(14), dp(12));
        input.setBackground(rounded(color(R.color.surface), color(R.color.line), 10));
        input.setMinHeight(dp(52));
    }

    private void buildLayout() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(color(R.color.surface));
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            int left, top, right, bottom;
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets visible = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                left = visible.left; top = visible.top; right = visible.right; bottom = visible.bottom;
            } else {
                left = insets.getSystemWindowInsetLeft(); top = insets.getSystemWindowInsetTop();
                right = insets.getSystemWindowInsetRight(); bottom = insets.getSystemWindowInsetBottom();
            }
            v.setPadding(left, top, right, bottom);
            return insets;
        });
        if (Build.VERSION.SDK_INT >= 30) getWindow().setDecorFitsSystemWindows(false);
        setContentView(root);
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(16), dp(4), dp(8), dp(4));
        TextView title = new TextView(this);
        title.setText("❯  PlexPort");
        title.setTextSize(20);
        title.setTextColor(color(R.color.text));
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        toolbar.addView(title, new LinearLayout.LayoutParams(0, dp(48), 1));
        title.setGravity(Gravity.CENTER_VERTICAL);
        Button menu = new Button(this);
        menu.setText("Menu");
        menu.setTextColor(color(R.color.accent));
        menu.setBackground(rounded(color(R.color.card), color(R.color.line), 10));
        menu.setContentDescription("PlexPort-menu: NAS-adres, opnieuw laden en afmelden");
        menu.setOnClickListener(v -> showMenu(menu));
        toolbar.addView(menu, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(48)));
        root.addView(toolbar);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setVisibility(View.GONE);
        root.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(3)));
        content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        errorPanel = new LinearLayout(this);
        errorPanel.setOrientation(LinearLayout.VERTICAL);
        errorPanel.setGravity(Gravity.CENTER);
        errorPanel.setPadding(dp(28), dp(24), dp(28), dp(24));
        errorPanel.setBackgroundColor(color(R.color.surface));
        errorTitle = new TextView(this);
        errorTitle.setTextColor(color(R.color.text));
        errorTitle.setTextSize(22);
        errorTitle.setGravity(Gravity.CENTER);
        errorPanel.addView(errorTitle);
        errorMessage = new TextView(this);
        errorMessage.setTextColor(color(R.color.text));
        errorMessage.setTextSize(16);
        errorMessage.setGravity(Gravity.CENTER);
        errorMessage.setPadding(0, dp(16), 0, dp(24));
        errorPanel.addView(errorMessage);
        Button retry = new Button(this);
        retry.setText("Opnieuw proberen");
        retry.setOnClickListener(v -> loadServer());
        errorPanel.addView(retry);
        Button address = new Button(this);
        address.setText("NAS-adres wijzigen");
        address.setOnClickListener(v -> showAddressDialog(false));
        errorPanel.addView(address);
        errorPanel.setVisibility(View.GONE);
        content.addView(errorPanel, new FrameLayout.LayoutParams(-1, -1));
    }

    @SuppressWarnings("deprecation")
    private void createWebView() {
        // No password persistence or untrusted native bridge is used.
        WebViewDatabase.getInstance(this).clearHttpAuthUsernamePassword();
        webView = new WebView(this);
        WebView.setWebContentsDebuggingEnabled(false);
        webView.setBackgroundColor(color(R.color.surface));
        webView.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setSaveFormData(false);
        settings.setSavePassword(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setGeolocationEnabled(false);
        settings.setSupportMultipleWindows(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setSafeBrowsingEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        if (Build.VERSION.SDK_INT >= 33) settings.setAlgorithmicDarkeningAllowed(false);
        CookieManager.getInstance().setAcceptCookie(false);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        webView.setWebViewClient(new ServerClient());
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int value) { progress.setProgress(value); }
            @Override public void onPermissionRequest(PermissionRequest request) { request.deny(); }
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                    FileChooserParams parameters) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                // Torrent MIME types are often missing on Android document providers.
                intent.setType("*/*");
                try { startActivityForResult(intent, PICK_TORRENT); }
                catch (android.content.ActivityNotFoundException e) {
                    fileCallback.onReceiveValue(null);
                    fileCallback = null;
                    Toast.makeText(MainActivity.this, "Er is geen bestandskiezer beschikbaar.", Toast.LENGTH_LONG).show();
                }
                return true;
            }
        });
        webView.setDownloadListener((url, userAgent, disposition, mime, length) ->
                Toast.makeText(this, "Gebruik de downloadknop in PlexPort. Je NAS en qBittorrent voeren de download uit.", Toast.LENGTH_LONG).show());
        content.addView(webView, 0, new FrameLayout.LayoutParams(-1, -1));
    }

    private void showMenu(View anchor) {
        PopupMenu menu = new PopupMenu(this, anchor);
        menu.getMenu().add("NAS-adres wijzigen").setOnMenuItemClickListener(item -> { showAddressDialog(false); return true; });
        menu.getMenu().add("Opnieuw laden").setOnMenuItemClickListener(item -> { loadServer(); return true; });
        menu.getMenu().add("Afmelden").setOnMenuItemClickListener(item -> {
            clearSession();
            destroyWebView();
            createWebView();
            showError("Je bent afgemeld", "Kies ‘Opnieuw proberen’ om weer bij PlexPort aan te melden.");
            return true;
        });
        menu.show();
    }

    private void showAddressDialog(boolean firstLaunch) {
        EditText address = new EditText(this);
        address.setSingleLine(true);
        address.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        address.setText(server);
        address.setSelectAllOnFocus(true);
        LinearLayout fields = new LinearLayout(this);
        fields.setOrientation(LinearLayout.VERTICAL);
        fields.setPadding(dp(24), dp(12), dp(24), 0);
        TextView help = new TextView(this);
        help.setText("De app gebruikt dezelfde bronnen, downloads en Plex-instellingen als de website op je NAS. Verbind met je thuisnetwerk. Gebruik http:// of https://.");
        fields.addView(help);
        fields.addView(address);
        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Je PlexPort op de NAS")
                .setView(fields)
                .setNegativeButton(firstLaunch ? "Sluiten" : "Annuleren", (d, w) -> { if (firstLaunch) finish(); })
                .setPositiveButton("Verbinden", null).create();
        dialog.setCanceledOnTouchOutside(false);
        if (firstLaunch) dialog.setOnCancelListener(d -> finish());
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                String chosen = ServerAddress.normalize(address.getText().toString());
                if (!chosen.equals(server)) { clearSession(); destroyWebView(); server = chosen; createWebView(); }
                preferences.edit().putString("server", chosen).apply();
                server = chosen;
                dialog.dismiss();
                loadServer();
            } catch (IllegalArgumentException e) { address.setError(e.getMessage()); }
        }));
        dialog.show();
    }

    private void loadServer() {
        if (sessionUser == null || sessionPassword == null) {
            showLoginDialog();
            return;
        }
        pageFailed = false;
        errorPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        webView.loadUrl(server);
    }

    private void clearSession() {
        sessionUser = null;
        sessionPassword = null;
        loginEpoch++;
    }

    private void showError(String title, String message) {
        if (finishing) return;
        pageFailed = true;
        handler.removeCallbacks(connectionTimeout);
        progress.setVisibility(View.GONE);
        errorTitle.setText(title);
        errorMessage.setText(message);
        errorPanel.setVisibility(View.VISIBLE);
        if (webView != null) webView.setVisibility(View.GONE);
    }

    private final class ServerClient extends WebViewClient {
        @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            if (ServerAddress.sameOrigin(server, request.getUrl().toString())) return false;
            Toast.makeText(MainActivity.this, "Deze app opent alleen jouw ingestelde PlexPort-server.", Toast.LENGTH_SHORT).show();
            return true;
        }
        @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            if (ServerAddress.sameOrigin(server, request.getUrl().toString())) return null;
            byte[] body = "Niet toegestaan".getBytes(StandardCharsets.UTF_8);
            return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden",
                    Collections.emptyMap(), new ByteArrayInputStream(body));
        }
        @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
            pageFailed = false;
            webAuthAttempts = 0;
            progress.setVisibility(View.VISIBLE);
            handler.removeCallbacks(connectionTimeout);
            handler.postDelayed(connectionTimeout, 20000);
        }
        @Override public void onPageFinished(WebView view, String url) {
            handler.removeCallbacks(connectionTimeout);
            progress.setVisibility(View.GONE);
            if (!pageFailed) { errorPanel.setVisibility(View.GONE); view.setVisibility(View.VISIBLE); }
        }
        @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request.isForMainFrame()) showError("PlexPort is niet bereikbaar",
                    "Controleer je wifi of VPN, het NAS-adres en of PlexPort op je NAS draait. Daarna kun je opnieuw proberen.");
        }
        @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
            if (!request.isForMainFrame()) return;
            if (response.getStatusCode() == 401) showError("Aanmelding nodig", "Probeer opnieuw en gebruik je PlexPort-gebruikersnaam en wachtwoord.");
            else if (response.getStatusCode() >= 400) showError("PlexPort geeft een fout", "Je NAS antwoordt met foutcode " + response.getStatusCode() + ". Controleer de PlexPort-app op TrueNAS.");
        }
        @Override public void onReceivedSslError(WebView view, SslErrorHandler sslHandler, SslError error) {
            sslHandler.cancel();
            showError("De beveiligde verbinding is ongeldig", "Het HTTPS-certificaat is niet geldig voor dit NAS-adres. Herstel het certificaat of gebruik het bestaande HTTP-adres op je vertrouwde thuisnetwerk.");
        }
        @Override public void onReceivedHttpAuthRequest(WebView view, HttpAuthHandler auth, String host, String realm) {
            if (!URI.create(server).getHost().equalsIgnoreCase(host) || sessionUser == null
                    || sessionPassword == null || ++webAuthAttempts > 1) {
                auth.cancel();
                clearSession();
                showError("Aanmelding verlopen", "Meld je opnieuw aan om PlexPort te gebruiken.");
                return;
            }
            auth.proceed(sessionUser, sessionPassword);
        }
    }

    private void showLoginDialog() {
        cancelAuth();
        LinearLayout fields = new LinearLayout(MainActivity.this);
        fields.setOrientation(LinearLayout.VERTICAL);
        fields.setPadding(dp(24), dp(24), dp(24), dp(8));
        fields.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        TextView brand = new TextView(this);
        brand.setText("❯  PlexPort");
        brand.setTextColor(color(R.color.accent));
        brand.setTextSize(18);
        brand.setTypeface(null, android.graphics.Typeface.BOLD);
        fields.addView(brand);
        TextView welcome = new TextView(this);
        welcome.setText("Welkom terug");
        welcome.setTextSize(28);
        welcome.setTextColor(color(R.color.text));
        welcome.setTypeface(null, android.graphics.Typeface.BOLD);
        welcome.setPadding(0, dp(22), 0, dp(8));
        fields.addView(welcome);
        TextView note = new TextView(MainActivity.this);
        note.setText("Meld je aan bij jouw mediaruimte.");
        note.setTextSize(14);
        note.setTextColor(color(R.color.muted));
        fields.addView(note);
        TextView serverLabel = new TextView(this);
        serverLabel.setText(server);
        serverLabel.setTextSize(12);
        serverLabel.setTextColor(color(R.color.muted));
        serverLabel.setPadding(dp(12), dp(10), dp(12), dp(10));
        serverLabel.setBackground(rounded(color(R.color.surface), color(R.color.line), 8));
        LinearLayout.LayoutParams serverParams = new LinearLayout.LayoutParams(-1, -2);
        serverParams.topMargin = dp(18);
        fields.addView(serverLabel, serverParams);
        loginLabel(fields, "Gebruikersnaam");
        EditText user = new EditText(MainActivity.this);
        user.setSingleLine(true);
        user.setHint("Gebruikersnaam");
        user.setText("admin");
        user.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
        styleInput(user);
        fields.addView(user);
        loginLabel(fields, "PlexPort-wachtwoord");
        EditText password = new EditText(MainActivity.this);
        password.setSingleLine(true);
        password.setHint("Vul je wachtwoord in");
        password.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        styleInput(password);
        fields.addView(password);
        CheckBox showPassword = new CheckBox(this);
        showPassword.setText("Toon wachtwoord");
        showPassword.setTextSize(13);
        showPassword.setTextColor(color(R.color.muted));
        showPassword.setMinHeight(dp(48));
        showPassword.setOnCheckedChangeListener((button, checked) -> {
            int selection = password.getSelectionStart();
            password.setInputType(InputType.TYPE_CLASS_TEXT | (checked ? InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD : InputType.TYPE_TEXT_VARIATION_PASSWORD));
            password.setSelection(Math.max(0, selection));
        });
        fields.addView(showPassword);
        TextView feedback = new TextView(MainActivity.this);
        feedback.setTextSize(14);
        feedback.setTextColor(color(R.color.error));
        feedback.setPadding(0, dp(12), 0, dp(8));
        feedback.setVisibility(View.GONE);
        fields.addView(feedback);
        TextView privacy = new TextView(this);
        privacy.setText("Gebruik je PlexPort-wachtwoord. Je wachtwoord wordt niet opgeslagen op je telefoon.");
        privacy.setTextSize(12);
        privacy.setTextColor(color(R.color.muted));
        privacy.setPadding(0, dp(10), 0, dp(12));
        fields.addView(privacy);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(fields);
        authDialog = new AlertDialog.Builder(MainActivity.this)
                .setView(scroll).setNegativeButton("Annuleren", (d, w) -> {
                    cancelAuth();
                    showError("Je bent niet aangemeld", "Kies ‘Opnieuw proberen’ om aan te melden.");
                }).setPositiveButton("Aanmelden", null).create();
        authDialog.setOnCancelListener(d -> {
            cancelAuth();
            showError("Je bent niet aangemeld", "Kies ‘Opnieuw proberen’ om aan te melden.");
        });
        authDialog.setOnShowListener(d -> {
            authDialog.getWindow().setBackgroundDrawable(rounded(color(R.color.card), color(R.color.line), 20));
            Button signIn = authDialog.getButton(AlertDialog.BUTTON_POSITIVE);
            signIn.setTextColor(android.graphics.Color.WHITE);
            signIn.setAllCaps(false);
            signIn.setBackgroundTintList(null);
            signIn.setBackground(rounded(0xff6366f1, 0, 10));
            signIn.setPadding(dp(20), dp(10), dp(20), dp(10));
            signIn.setMinHeight(dp(48));
            signIn.setOnClickListener(v -> {
            if (user.getText().toString().trim().isEmpty()) { user.setError("Vul je gebruikersnaam in."); return; }
            if (password.getText().length() == 0) { password.setError("Vul je PlexPort-wachtwoord in."); return; }
            String chosenUser = user.getText().toString().trim();
            String chosenPassword = password.getText().toString();
            String chosenServer = server;
            int attemptEpoch = ++loginEpoch;
            AlertDialog dialog = authDialog;
            feedback.setVisibility(View.GONE);
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
            loginExecutor.execute(() -> {
                String error = verifyLogin(chosenServer, chosenUser, chosenPassword);
                handler.post(() -> {
                    if (finishing || attemptEpoch != loginEpoch || dialog != authDialog) return;
                    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);
                    if (error != null) {
                        feedback.setText(error);
                        feedback.setVisibility(View.VISIBLE);
                        return;
                    }
                    sessionUser = chosenUser;
                    sessionPassword = chosenPassword;
                    password.getText().clear();
                    dialog.dismiss();
                    authDialog = null;
                    loadServer();
                });
            });
            });
        });
        authDialog.setCanceledOnTouchOutside(false);
        authDialog.show();
    }

    private String verifyLogin(String origin, String user, String password) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) URI.create(origin).toURL().openConnection();
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            connection.setInstanceFollowRedirects(false);
            connection.setUseCaches(false);
            String basic = android.util.Base64.encodeToString((user + ":" + password)
                    .getBytes(StandardCharsets.UTF_8), android.util.Base64.NO_WRAP);
            connection.setRequestProperty("Authorization", "Basic " + basic);
            int status = connection.getResponseCode();
            if (status == 200) return null;
            if (status == 401 || status == 403) return "De gebruikersnaam of het PlexPort-wachtwoord klopt niet.";
            if (status >= 300 && status < 400) return "Dit adres stuurt door. Vul het directe PlexPort-adres in.";
            return "PlexPort geeft foutcode " + status + ". Controleer de app op je NAS.";
        } catch (javax.net.ssl.SSLException e) {
            return "Het HTTPS-certificaat is ongeldig. Herstel het certificaat op je NAS.";
        } catch (Exception e) {
            return "PlexPort is niet bereikbaar. Controleer wifi of VPN en het NAS-adres.";
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private void cancelAuth() {
        loginEpoch++;
        if (authDialog != null) { authDialog.dismiss(); authDialog = null; }
    }

    private void destroyWebView() {
        handler.removeCallbacks(connectionTimeout);
        cancelAuth();
        if (fileCallback != null) { fileCallback.onReceiveValue(null); fileCallback = null; }
        if (webView != null) {
            webView.stopLoading();
            content.removeView(webView);
            webView.clearHistory();
            webView.destroy();
            webView = null;
        }
        WebViewDatabase.getInstance(this).clearHttpAuthUsernamePassword();
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_TORRENT && fileCallback != null) {
            Uri selected = resultCode == RESULT_OK && data != null ? data.getData() : null;
            fileCallback.onReceiveValue(selected != null ? new Uri[] {selected} : null);
            fileCallback = null;
        }
    }

    private void handleBack() {
        if (webView != null && errorPanel.getVisibility() != View.VISIBLE && webView.canGoBack()) webView.goBack();
        else finish();
    }
    // API 33+ uses the native dispatcher registered in onCreate; this fallback serves Android 8–12.
    @SuppressLint("GestureBackNavigation")
    @SuppressWarnings("deprecation") @Override public void onBackPressed() { handleBack(); }
    @Override protected void onDestroy() {
        finishing = true;
        clearSession();
        loginExecutor.shutdownNow();
        destroyWebView();
        super.onDestroy();
    }
}
