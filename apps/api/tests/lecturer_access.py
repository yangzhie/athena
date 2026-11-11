"""Explicit local administrator provisioning for tests; no HTTP role bypass."""

def make_lecturer(client):
    identity = client.get('/identity')
    client.identity_cookie = identity.headers.get('set-cookie', '')
    spaces = client.app.state.spaces
    invite = spaces.create_lecturer_invite()
    response = client.post('/identity/lecturer-access', json={'code': invite})
    assert response.status_code == 200 and response.json()['role'] == 'lecturer'
    return client
