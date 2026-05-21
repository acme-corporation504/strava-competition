### strava segment tracker

- python script that extracts strava segment times for authenticated users

**To Do**
- find better way to store refresh tokens (done - store as json)

### usage
- need to get refresh tokens from each user
- users authenticate using the following site: https://www.strava.com/oauth/authorize?client_id=245963&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=read_all
- will lead users to an authentication page
- once authenticated, will take the user to a broken page
- extract the link from the broken page (should look like: http://localhost/?state=&code=a1b2c3d4e5f6g7h8i9j0...&scope=read,activity:read_all)
- extract the code from the link and use as refresh code

### create a .env file
- store your client ID and client secrete (from strava api)
```
nano .env
CLIENT_ID="123456"
CLIENT_SECRET="123456789ABCDefghIJKLmnopQRSTuvwxYZ"

```
### create a tokens.json file
- store refresh tokens
- add temp refresh tokens as you get them from your users
```
nano tokens.json
{
	"12345678":"123456789ABCDefghIJKLmnopQRSTuvwxYZ"
}
```

### edit .gitignore file
```
nano .gitignore
.env
tokens.json
```