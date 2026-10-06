package tj.donatix.app;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Parcel;
import java.util.Arrays;
import java.util.List;

/**
 * Открывает Donatix как приложение: через Chrome (Trusted Web Activity — без адресной строки,
 * с push-уведомлениями). Нет подходящего браузера или что-то пошло не так — своё окно WebActivity.
 */
public class LauncherActivity extends Activity {
    static final String HOME = "https://donatix.tj/panel?source=app";
    private static final String SERVICE_ACTION = "android.support.customtabs.action.CustomTabsService";
    private static final String SERVICE_DESC = "android.support.customtabs.ICustomTabsService";
    private static final String CALLBACK_DESC = "android.support.customtabs.ICustomTabsCallback";
    private static final List<String> PREFERRED = Arrays.asList(
            "com.android.chrome", "com.chrome.beta", "com.chrome.dev", "com.google.android.apps.chrome",
            "com.microsoft.emmx", "com.sec.android.app.sbrowser", "com.brave.browser", "com.opera.browser");

    private ServiceConnection connection;
    private boolean launched;
    private final Handler handler = new Handler(Looper.getMainLooper());

    /** Пустой «обратный вызов» для Chrome: он нужен, чтобы Chrome узнал наше приложение и проверил связь с сайтом. */
    static final class Callback extends Binder {
        Callback() { attachInterface(null, CALLBACK_DESC); }
        @Override protected boolean onTransact(int code, Parcel data, Parcel reply, int flags) {
            if (code == INTERFACE_TRANSACTION) { if (reply != null) reply.writeString(CALLBACK_DESC); return true; }
            if (reply != null) reply.writeNoException();
            return true;
        }
    }

    private final Callback callback = new Callback();

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        String url = HOME;
        Uri data = getIntent() != null ? getIntent().getData() : null;
        if (data != null && "donatix.tj".equals(data.getHost())) url = data.toString();
        final String target = url;
        String browser = pickBrowser();
        if (browser == null) { openWebView(target); return; }
        // Если Chrome не ответил за 4 секунды — не держим человека на заставке
        handler.postDelayed(new Runnable() { public void run() { if (!launched) openWebView(target); } }, 4000);
        bindBrowser(browser, target);
    }

    private String pickBrowser() {
        PackageManager pm = getPackageManager();
        List<ResolveInfo> services = pm.queryIntentServices(new Intent(SERVICE_ACTION), 0);
        String any = null;
        for (String p : PREFERRED) {
            for (ResolveInfo ri : services) if (ri.serviceInfo != null && p.equals(ri.serviceInfo.packageName)) return p;
        }
        for (ResolveInfo ri : services) if (ri.serviceInfo != null) { any = ri.serviceInfo.packageName; break; }
        return any;
    }

    private void bindBrowser(final String pkg, final String url) {
        connection = new ServiceConnection() {
            @Override public void onServiceConnected(ComponentName name, IBinder service) {
                boolean session = newSession(service);
                launchTwa(pkg, url, session);
            }
            @Override public void onServiceDisconnected(ComponentName name) { }
        };
        Intent i = new Intent(SERVICE_ACTION).setPackage(pkg);
        try {
            if (!bindService(i, connection, Context.BIND_AUTO_CREATE)) { connection = null; launchTwa(pkg, url, false); }
        } catch (Exception e) {
            connection = null; launchTwa(pkg, url, false);
        }
    }

    /** newSession(callback) у CustomTabsService. Номер вызова в разных версиях считается по-разному — пробуем оба. */
    private boolean newSession(IBinder service) {
        int[] codes = {IBinder.FIRST_CALL_TRANSACTION + 2, IBinder.FIRST_CALL_TRANSACTION + 1};
        for (int code : codes) {
            Parcel data = Parcel.obtain(), reply = Parcel.obtain();
            try {
                data.writeInterfaceToken(SERVICE_DESC);
                data.writeStrongBinder(callback);
                service.transact(code, data, reply, 0);
                reply.readException();
                if (reply.readInt() != 0) return true;
            } catch (Exception ignored) {
            } finally { data.recycle(); reply.recycle(); }
        }
        return false;
    }

    private void launchTwa(String pkg, String url, boolean session) {
        if (launched) return;
        launched = true;
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.setPackage(pkg);
            Bundle extras = new Bundle();
            extras.putBinder("android.support.customtabs.extra.SESSION", session ? callback : null);
            intent.putExtras(extras);
            intent.putExtra("android.support.customtabs.extra.LAUNCH_AS_TRUSTED_WEB_ACTIVITY", true);
            intent.putExtra("android.support.customtabs.extra.TOOLBAR_COLOR", 0xFF4338CA);
            intent.putExtra("android.support.customtabs.extra.NAVIGATION_BAR_COLOR", 0xFFFFFFFF);
            intent.putExtra("androidx.browser.customtabs.extra.SHARE_STATE", 2);   // без кнопки «Поделиться»
            intent.putExtra("android.support.customtabs.extra.TITLE_VISIBILITY", 0);
            startActivity(intent);
            overridePendingTransition(0, 0);
            finish();
        } catch (Exception e) {
            launched = false;
            openWebView(url);
        }
    }

    private void openWebView(String url) {
        if (launched && isFinishing()) return;
        launched = true;
        startActivity(new Intent(this, WebActivity.class).putExtra("url", url));
        overridePendingTransition(0, 0);
        finish();
    }

    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (connection != null) { try { unbindService(connection); } catch (Exception ignored) { } }
        super.onDestroy();
    }
}
