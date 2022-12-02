import time
import asyncio
import argparse
from hashlib import sha256
#from flask_cors import CORS
from hfc.fabric import Client
from flask import Flask, request, jsonify, session
app = Flask(__name__)
#CORS(app, resources=r'/*')
loop = asyncio.get_event_loop()
cli = Client(net_profile="network.json")
org1_admin = cli.get_user('org1.example.com', 'Admin')
cli.new_channel('mychannel')


def spilt_data(message):
    message = message.split(',')
    return_dict = {}
    for mess in message:
        temp = mess.split(':')
        return_dict[temp[0]] = temp[1]
    return return_dict


def get_cert(key):
    response = loop.run_until_complete(cli.chaincode_query(
        requestor=org1_admin,
        channel_name='mychannel',
        peers=['peer0.org1.example.com'],
        args=[key],
        cc_name='sacc'
    ))
    return response


def join_dict(mess_dict):
    res = ''
    for key in mess_dict.keys():
        if res != '':
            res = res + ','
        res = res + str(key) + ':' + mess_dict[key]
    return res


def up(key, mess):
    loop.run_until_complete(cli.chaincode_invoke(
        requestor=org1_admin,
        channel_name='mychannel',
        peers=['peer0.org1.example.com'],
        args=[key, mess],
        cc_name='sacc',
        fcn='set',
    ))


def add_count(file_type):
    try:
        response = loop.run_until_complete(cli.chaincode_query(
            requestor=org1_admin,
            channel_name='mychannel',
            peers=['peer0.org1.example.com'],
            args=[file_type],
            cc_name='sacc'
        ))
        loop.run_until_complete(cli.chaincode_invoke(
            requestor=org1_admin,
            channel_name='mychannel',
            peers=['peer0.org1.example.com'],
            args=[file_type, str(int(response) + 1)],
            cc_name='sacc',
            fcn='set',
        ))
    except:
        loop.run_until_complete(cli.chaincode_invoke(
            requestor=org1_admin,
            channel_name='mychannel',
            peers=['peer0.org1.example.com'],
            args=[file_type, '1'],
            cc_name='sacc',
            fcn='set',
        ))


# img raw_file 与该证照的key绑定
@app.route('/upChain', methods=["POST"])
def img_up():
    data = request.get_json()
    message = data.get('File')
    data = dict(message)
    file_type = data['type']
    key = data['id']
    file_hash = data['fileHash']
    info_hash = data['infoHash']
    cert_mess = 'Name:' + data['name'] + ',FileName:' + data['fileName'] + ',Mess:' + data['info'] + ',Type:' + file_type + \
           ',Status:1,Front_index:-1,Back_index:-1'
    # 查询改证照是否存在
    try:
        loop.run_until_complete(cli.chaincode_query(
            requestor=org1_admin,
            channel_name='mychannel',
            peers=['peer0.org1.example.com'],
            args=[key],
            cc_name='sacc'
        ))
        res = {'success': False, 'code': 10001, 'message': '文件上链失败,证照已存在！', 'data': None, 'time': time.time()}
    except:
        add_count(file_type)
        loop.run_until_complete(cli.chaincode_invoke(
            requestor=org1_admin,
            channel_name='mychannel',
            peers=['peer0.org1.example.com'],
            args=[key, cert_mess],
            cc_name='sacc',
            fcn='set',
        ))
        # 建立file_hash与key的关系
        loop.run_until_complete(cli.chaincode_invoke(
            requestor=org1_admin,
            channel_name='mychannel',
            peers=['peer0.org1.example.com'],
            args=[file_hash, key],
            cc_name='sacc',
            fcn='set',
        ))
        # 建立info_hash和key关系
        loop.run_until_complete(cli.chaincode_invoke(
            requestor=org1_admin,
            channel_name='mychannel',
            peers=['peer0.org1.example.com'],
            args=[info_hash, key],
            cc_name='sacc',
            fcn='set',
        ))
        res = {'success': True, 'code': 200, 'message': '文件上链成功！', 'data': cert_mess, 'time': time.time()}
    return jsonify({"code": 200, "msg": res})


@app.route('/updateChain', methods=["POST"])
def update():
    data = request.get_json()
    message = data.get('File')
    update_data = dict(message)
    key = update_data['id']
    try:
        # 获取最新
        message = get_cert(key)
        t_new_dict = spilt_data(message)
        # 最新的往前找一个
        if t_new_dict['Front_index'] != '-1':
            # 往前再取一个
            front_key = t_new_dict['Front_index']
            front = get_cert(t_new_dict['Front_index'])
            front_dict = spilt_data(front)
            # 修改向后索引
            front_self_key = front_key.split('_')
            front_dict['Back_index'] = front_self_key[0] + '_' + str(int(front_self_key[1]) + 1)
            front_mess = join_dict(front_dict)
            up(front_key, front_mess)
            # 修改最新的节点
            t_new_key = front_dict['Back_index']
            t_new_mess = get_cert(key)
            t_new_dict = spilt_data(t_new_mess)
            t_new_dict['Status'] = '0'
            t_new_dict['Back_index'] = key
            raw_file = t_new_dict['Mess']
            t_file_hash = t_new_dict['fileHash']
            t_info_hash = t_new_dict['infoHash']
            t_new_mess = join_dict(t_new_dict)
            up(t_new_key, t_new_mess)
            up(t_file_hash, t_new_key)
            up(t_info_hash, t_new_key)
            # 加入新的节点
            cert_mess = 'Name:' + update_data['name'] + ',FileName:' + update_data['fileName'] + ',Mess:' + \
                        update_data['info'] + ',Type:' + update_data['Type'] + ',Status:1,Front_index:' + t_new_key + \
                        ',Back_index:-1'
            up(key, cert_mess)
            up(update_data['fileHash'], key)
            up(update_data['infoHash'], key)

        else:
            front_key = key + '_1'
            update_data['Back_index'] = key
            update_data['Status'] = '0'
            front_mess = join_dict(update_data)
            up(front_key, front_mess)
            cert_mess = 'Name:' + update_data['name'] + ',FileName:' + update_data['fileName'] + 'Mess:' + update_data['info']\
                        + ',Type:' + update_data['Type'] + ',Status:1,Front_index:' + front_key + ',Back_index:-1'
            up(key, cert_mess)
        res = {'success': True, 'code': 200, 'message': '文件更新成功！', 'data': cert_mess, 'time': time.time()}
    except Exception as e:
        print(e)
        res = {'success': False, 'code': 10001, 'message': '文件更新失败！', 'data': None, 'time': time.time()}
    return jsonify({"code": 200, "msg": res})


# get_new
@app.route('/getLatestValueByKey', methods=["POST"])
def key_search():
    data = request.get_json()
    key = data.get('Key')
    try:
        response = loop.run_until_complete(cli.chaincode_query(
                requestor=org1_admin,
                channel_name='mychannel',
                peers=['peer0.org1.example.com'],
                args=[key],
                cc_name='sacc'
            ))
        message = spilt_data(response)
        res = {'success': True, 'code': 200, 'message': '数据查询成功！', 'data': message, 'time': time.time()}
    except Exception as e:
        print(e)
        res = {'success': False, 'code': 10001, 'message': '数据查询失败！', 'data': None, 'time': time.time()}
    return jsonify({"code": 200, "msg": res})


# get_his_key
@app.route('/getListByKey', methods=["POST"])
def history_key():
    data = request.get_json()
    key = data.get('Key')
    try:
        message = get_cert(key)
        mess_dict = spilt_data(message)
        return_data = [mess_dict]
        while mess_dict['Front_index'] != '-1':
            front_certificate = get_cert(mess_dict['Front_index'])
            mess_dict = spilt_data(front_certificate)
            return_data.append(mess_dict)
        res = {'success': True, 'code': 200, 'message': '数据查询成功！', 'data': {key: return_data}, 'time': time.time()}
    except Exception as e:
        print(e)
        res = {'success': False, 'code': 10001, 'message': '数据查询失败！', 'data': None, 'time': time.time()}
    return jsonify({"code": 200, "msg": res})


# get_his_hash
@app.route('/getListByHash', methods=["POST"])
def history_hash():
    data = request.get_json()
    hash_mess = data.get('Key')
    try:
        key = loop.run_until_complete(cli.chaincode_query(
                requestor=org1_admin,
                channel_name='mychannel',
                peers=['peer0.org1.example.com'],
                args=[hash_mess],
                cc_name='sacc'
            ))
        message = get_cert(key)
        mess_dict = spilt_data(message)
        back_key = mess_dict['Back_index']
        while mess_dict['Back_index'] != '-1':
            back_certificate = get_cert(back_key)
            mess_dict = spilt_data(back_certificate)
        return_data = [mess_dict]
        while mess_dict['Front_index'] != '-1':
            front_certificate = get_cert(mess_dict['Front_index'])
            mess_dict = spilt_data(front_certificate)
            return_data.append(mess_dict)
        res = {'success': True, 'code': 200, 'message': '数据查询成功！', 'data': {hash_mess: return_data},
               'time': time.time()}
    except Exception as e:
        print(e)
        res = {'success': False, 'code': 10001, 'message': '数据查询失败！', 'data': None, 'time': time.time()}
    return jsonify({"code": 200, "msg": res})


# get_block_high
@app.route('/getMetaByKey', methods=["POST"])
def block_mess():
    data = request.get_json()
    key = data.get('Key')
    try:
        response = loop.run_until_complete(cli.query_block(
            requestor=org1_admin,
            channel_name='mychannel',
            peers=['peer0.org1.example.com'],
            block_number=key,
            decode=True
        ))
        data = response['data']
        data1 = data['data'][0]['payload']['header']['channel_header']
        tran_time = data1['timestamp'].split(' ')[0]
        tran_tx = data1['tx_id']
        data2 = data['data'][0]['payload']['data']['actions'][0]
        tran_creat = data2['header']['creator']['mspid']
        up_data = data2['payload']['action']['proposal_response_payload']['extension']['response']['payload']
        res_data = {'tran_time': tran_time, 'tran_tx': tran_tx, 'tran_creater': tran_creat, 'up_data': str(up_data)}
        res = {'success': True, 'code': 200, 'message': '区块查询成功！', 'data': res_data, 'time': time.time()}
    except Exception as e:
        print(e)
        res = {'success': False, 'code': 10001, 'message': '区块查询失败！', 'data': None, 'time': time.time()}
    return jsonify({"code": 200, "msg": res})


# get_chain_mess
@app.route('/getChainSummary', methods=["POST"])
def chain_mess():
    data = request.get_json()
    response = loop.run_until_complete(cli.query_peers(
               requestor=org1_admin,
               peer='peer0.org1.example.com',
               channel='mychannel',
               local=False,
               decode=True
               ))
    res = {'success': True, 'code': 200, 'message': '区块查询成功！', 'data': response, 'time': time.time()}
    return jsonify({"code": 200, "msg": res})


# get_type_count
@app.route('/getTypeCount', methods=["POST"])
def type_count():
    data = request.get_json()
    file_type = data.get('Type')
    try:
        response = loop.run_until_complete(cli.chaincode_query(
                requestor=org1_admin,
                channel_name='mychannel',
                peers=['peer0.org1.example.com'],
                args=[file_type],
                cc_name='sacc'
            ))
        res = {'success': True, 'code': 200, 'message': '数据查询成功！', 'data': {file_type: response}, 'time': time.time()}
    except:
        res = {'success': True, 'code': 200, 'message': '数据查询成功！', 'data': {file_type: '0'}, 'time': time.time()}
    return jsonify({"code": 200, "msg": res})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="port config")
    parser.add_argument("--port", default=9000, type=int, help="port number")
    opt = parser.parse_args()
    app.run(host="0.0.0.0", port=opt.port, debug=True)
