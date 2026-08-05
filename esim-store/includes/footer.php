</main>
<footer class="site-footer">
    <div class="container footer-inner">
        <div>
            <strong><?= h($config['site_name']) ?></strong>
            <p class="muted">Виртуальные eSIM для путешествий — мгновенная активация, без физической SIM-карты.</p>
        </div>
        <div>
            <div class="muted">Поддержка</div>
            <?php if (!empty($config['support_phone'])): ?>
                <div><?= h($config['support_phone']) ?></div>
            <?php endif; ?>
            <div><?= h($config['support_email']) ?></div>
        </div>
        <div>
            <a href="<?= h(url('admin/index.php')) ?>" class="muted admin-link">Вход для администратора</a>
        </div>
    </div>
</footer>
<?php if (!empty($config['zadarma_widget_key'])): ?>
    <!-- Zadarma WebRTC support widget. Uses the public widget key only (not the API secret). -->
    <script>
        (function (w, d, k) {
            w.zadarmaWidgetKey = k;
            var s = d.createElement('script');
            s.async = true;
            s.src = 'https://webtel.zadarma.com/widget/widget.js';
            d.body.appendChild(s);
        })(window, document, <?= json_encode($config['zadarma_widget_key']) ?>);
    </script>
<?php endif; ?>
</body>
</html>
