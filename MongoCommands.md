## Random list of usefull stuff


## Users and Roles

```js
db.getRole("appAdmin", { showPrivileges: true })

  db.getUsers()

```
Admin login once users and roles are created

```bash
podman exec -it clutter_base_devel  mongosh clutter_base -u clutter_admin -p --eval
```


Add new user

```js
db.createUser({user : "jmacey", pwd : "password", roles : [{role: 'readWrite', db: 'clutter_base'}]})
db.createRole
```

```
uv run clutter_base/src/clutter_base/cli/admin.py create-user --username jmacey --password
```