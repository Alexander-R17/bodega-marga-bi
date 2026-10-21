from types import SimpleNamespace
import pandas as pd
import pytest
import bodega.staff as staff
from bodega.auth import AccessError


@pytest.fixture
def cloud(monkeypatch):
    monkeypatch.setattr(staff, "mode", lambda: "cloud")
    monkeypatch.setattr(staff, "require_identity", lambda: {"uid": "admin"})
    monkeypatch.setattr(staff, "assigned_roles", lambda: {"admin@test.invalid": "administrador", "cash@test.invalid": "cajero"})


def test_history_resolves_each_actor_and_keeps_original_ids(cloud, monkeypatch):
    profiles={"admin": {"name": "Alexander", "email": "admin@test.invalid"},
              "cash": {"name": "María", "email": "cash@test.invalid"}}
    monkeypatch.setattr(staff, "profiles_for", lambda uids: profiles)
    original=pd.DataFrame({"id": [1,2,3], "usuario_uid": ["cash","admin","deleted"],
                           "pago_confirmado_por": ["cash","admin",None]})
    visible=staff.present_activity(original)
    assert visible.Responsable.tolist()==["María","Alexander","Usuario sin nombre"]
    assert visible["Rol actual"].tolist()==["Cajero","Administrador","Sin rol asignado"]
    assert visible["Pago confirmado por"].tolist()==["María","Alexander","Sin registro"]
    assert "usuario_uid" not in visible and "pago_confirmado_por" not in visible
    assert original.usuario_uid.tolist()==["cash","admin","deleted"]


def test_failed_directory_does_not_attribute_rows_to_current_user(cloud, monkeypatch):
    def failed(*args):raise RuntimeError("PRIVATE_DATA_MUST_NOT_LEAK")
    monkeypatch.setattr(staff, "_profiles", failed)
    result=staff.present_activity(pd.DataFrame({"usuario_uid": ["other", "deleted"]}))
    assert result.Responsable.tolist()==["Usuario sin nombre","Usuario sin nombre"]
    assert "PRIVATE_DATA" not in result.to_csv()


def test_bulk_users_are_joined_by_uid_not_response_order(monkeypatch):
    from firebase_admin import auth
    staff._profiles.clear()
    calls=[]
    def get_users(identifiers, **kwargs):
        calls.append(len(identifiers))
        return SimpleNamespace(users=[SimpleNamespace(uid=item.uid, display_name="Nombre "+item.uid,
                                                     email="mail@test.invalid") for item in reversed(identifiers)])
    monkeypatch.setattr(auth, "get_users", get_users)
    monkeypatch.setattr(staff, "firebase_app", lambda: "fake-app")
    profiles=staff._profiles("test-project",tuple(f"u{x}" for x in range(201)))
    assert calls==[100,100,1]
    assert profiles["u0"]["name"]=="Nombre u0" and profiles["u200"]["name"]=="Nombre u200"
    staff._profiles.clear()


def test_only_admin_can_set_team_names(monkeypatch):
    def denied(*roles):raise AccessError("Sin permiso")
    monkeypatch.setattr(staff, "require_role", denied)
    with pytest.raises(AccessError,match="Sin permiso"):staff.save_staff_name("target","Alexander")


def test_name_update_checks_target_and_only_changes_display_name(monkeypatch):
    from firebase_admin import auth
    monkeypatch.setattr(staff, "require_role", lambda *roles: {"role":"administrador"})
    monkeypatch.setattr(staff, "team_directory", lambda: {"member": {"name":"", "email":"m@test.invalid"}})
    monkeypatch.setattr(staff, "firebase_app", lambda: "fake-app")
    calls=[]
    monkeypatch.setattr(auth, "update_user", lambda uid, **kwargs: calls.append((uid,kwargs)))
    with pytest.raises(AccessError,match="equipo"):staff.save_staff_name("outsider","Alexander")
    assert not calls
    staff.save_staff_name("member","  Alexander   Ríos  ")
    assert calls==[("member",{"display_name":"Alexander Ríos","app":"fake-app"})]
