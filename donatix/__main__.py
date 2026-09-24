"""Команды:

    python -m donatix serve [--host 0.0.0.0] [--port 8000]   запустить сайт и API
    python -m donatix sync                                   обновить каталог у поставщика
    python -m donatix create-admin EMAIL                     создать админа (пароль спросит)
    python -m donatix check                                  проверить ключ поставщика и баланс
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="donatix")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("sync")
    sub.add_parser("check")
    admin = sub.add_parser("create-admin")
    admin.add_argument("email")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from . import accounts, catalog, db
    from .config import Config
    from .suppliers import SupplierError, make_supplier

    config = Config.from_env()

    if args.cmd == "serve":
        import uvicorn

        from .app import create_app

        uvicorn.run(create_app(config), host=args.host, port=args.port, proxy_headers=True,
                    forwarded_allow_ips="127.0.0.1")
        return 0

    db.init(config.db_path)
    conn = db.connect(config.db_path)
    try:
        if args.cmd == "sync":
            result = catalog.sync_catalog(conn, make_supplier(config))
            print(f"Готово: {result['products']} товаров, выключено {result['disabled']}.")
        elif args.cmd == "check":
            supplier = make_supplier(config)
            try:
                print(f"Поставщик: {supplier.name}. Баланс: ${supplier.balance()}")
            except SupplierError as exc:
                print(f"Ошибка: {exc}")
                return 1
        elif args.cmd == "create-admin":
            password = getpass.getpass("Пароль (мин. 8 символов): ")
            login = args.email.split("@")[0][:32]
            accounts.create_user(conn, email=args.email, login=login, password=password,
                                 role="admin", status="active")
            print(f"Админ {args.email} создан. Вход: /login")
    except accounts.AccountError as exc:
        print(f"Ошибка: {exc}")
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
